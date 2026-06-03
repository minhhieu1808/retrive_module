import os
import datetime
import urllib3
import warnings
from typing import Dict, Any, List, Optional
from elasticsearch import Elasticsearch
from fontTools.ttLib import TTFont

# Disable SSL verification warnings if user/pass is configured with self-signed certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class FontMetadataService:
    """Service to handle parsing font files and indexing their metadata into Elasticsearch."""
    
    def __init__(
        self, 
        es_url: Optional[str] = None, 
        es_user: Optional[str] = None, 
        es_password: Optional[str] = None
    ):
        # Load from arguments or fallback to environment variables
        self.es_url = es_url or os.getenv("ELASTICSEARCH_URL", "http://171.232.252.198:9200")
        
        # Force HTTP scheme and ensure it is present
        if self.es_url.lower().startswith("https://"):
            self.es_url = "http://" + self.es_url[8:]
        elif not self.es_url.lower().startswith("http://"):
            self.es_url = "http://" + self.es_url
            
        self.es_user = es_user or os.getenv("ELASTICSEARCH_USER", "elastic")
        self.es_password = es_password or os.getenv("ELASTICSEARCH_PASSWORD")
        
        # Configure connection parameters
        conn_params = {"hosts": [self.es_url]}
        
        # Basic Auth
        if self.es_user and self.es_password:
            conn_params["basic_auth"] = (self.es_user, self.es_password)
                
        self.es = Elasticsearch(**conn_params)

    def _mac_epoch_to_iso(self, seconds: int) -> Optional[str]:
        """Convert Mac epoch (seconds since 1904-01-01) used by fontTools to ISO 8601 string."""
        try:
            epoch = datetime.datetime(1904, 1, 1)
            dt = epoch + datetime.timedelta(seconds=seconds)
            return dt.isoformat() + "Z"
        except Exception:
            return None

    def create_index(self, index_name: str = "metadata") -> bool:
        """Create the metadata index with all possible font metadata field mappings if it doesn't exist."""
        index_mapping = {
            "mappings": {
                "properties": {
                    # Naming fields
                    "family": {
                        "type": "text", 
                        "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                    },
                    "subfamily": {"type": "keyword"},
                    "full_name": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                    },
                    "postscript_name": {"type": "keyword"},
                    "unique_id": {"type": "keyword"},
                    "version_string": {"type": "keyword"},
                    "copyright": {"type": "text"},
                    "trademark": {"type": "text"},
                    "manufacturer": {"type": "text"},
                    "designer": {"type": "text"},
                    "description": {"type": "text"},
                    "vendor_url": {"type": "keyword"},
                    "designer_url": {"type": "keyword"},
                    "license": {"type": "text"},
                    "license_url": {"type": "keyword"},
                    "typographic_family": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                    },
                    "typographic_subfamily": {"type": "keyword"},
                    "sample_text": {"type": "text"},
                    
                    # Font Header ('head' table)
                    "font_revision": {"type": "double"},
                    "units_per_em": {"type": "integer"},
                    "created_timestamp": {"type": "date"},
                    "modified_timestamp": {"type": "date"},
                    "bbox_xmin": {"type": "integer"},
                    "bbox_ymin": {"type": "integer"},
                    "bbox_xmax": {"type": "integer"},
                    "bbox_ymax": {"type": "integer"},
                    "mac_style_bold": {"type": "boolean"},
                    "mac_style_italic": {"type": "boolean"},
                    
                    # OS/2 Metrics & Info ('OS/2' table)
                    "weight_class": {"type": "integer"},
                    "width_class": {"type": "integer"},
                    "embedding_permissions_flags": {"type": "integer"},
                    "is_embeddable": {"type": "boolean"},
                    "typo_ascender": {"type": "integer"},
                    "typo_descender": {"type": "integer"},
                    "typo_line_gap": {"type": "integer"},
                    "win_ascent": {"type": "integer"},
                    "win_descent": {"type": "integer"},
                    "x_height": {"type": "integer"},
                    "cap_height": {"type": "integer"},
                    "vendor_id": {"type": "keyword"},
                    "panose_family_type": {"type": "integer"},
                    "panose_serif_style": {"type": "integer"},
                    "panose_weight": {"type": "integer"},
                    "panose_proportion": {"type": "integer"},
                    "panose_contrast": {"type": "integer"},
                    
                    # Postscript Info ('post' table)
                    "italic_angle": {"type": "double"},
                    "underline_position": {"type": "integer"},
                    "underline_thickness": {"type": "integer"},
                    "is_monospaced": {"type": "boolean"},
                    
                    # Maxp Info ('maxp' table)
                    "num_glyphs": {"type": "integer"},
                    
                    # Advanced / Added metadata
                    "supports_vietnamese": {"type": "boolean"},
                    "is_variable": {"type": "boolean"},
                    "tables_list": {"type": "keyword"},
                    "open_type_features": {"type": "keyword"},
                    "variable_axes": {
                        "type": "object",
                        "properties": {
                            "tag": {"type": "keyword"},
                            "min_value": {"type": "double"},
                            "max_value": {"type": "double"},
                            "default_value": {"type": "double"}
                        }
                    },
                    
                    # General File metadata
                    "file_name": {"type": "keyword"},
                    "file_path": {"type": "keyword"},
                    "file_size_bytes": {"type": "long"},
                    "format": {"type": "keyword"},
                    "indexed_at": {"type": "date"},
                    "error": {"type": "keyword"}
                }
            }
        }
        
        if self.es.indices.exists(index=index_name):
            print(f"Index '{index_name}' already exists. Skipping creation.")
            return False
            
        self.es.indices.create(index=index_name, body=index_mapping)
        print(f"Index '{index_name}' created successfully.")
        return True

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """Extract all available metadata from TTF, OTF, TTC, WOFF, or WOFF2 files using fontTools."""
        try:
            font = TTFont(file_path, fontNumber=0)
            metadata = {}
            
            # 1. Parse name table (Naming records)
            name_table = font.get('name')
            if name_table:
                # Name IDs Mapping dictionary
                name_id_map = {
                    0: 'copyright',
                    1: 'family',
                    2: 'subfamily',
                    3: 'unique_id',
                    4: 'full_name',
                    5: 'version_string',
                    6: 'postscript_name',
                    7: 'trademark',
                    8: 'manufacturer',
                    9: 'designer',
                    10: 'description',
                    11: 'vendor_url',
                    12: 'designer_url',
                    13: 'license',
                    14: 'license_url',
                    16: 'typographic_family',
                    17: 'typographic_subfamily',
                    19: 'sample_text'
                }
                
                for record in name_table.names:
                    try:
                        val = record.toUnicode()
                    except Exception:
                        continue
                    
                    name_id = record.nameID
                    if name_id in name_id_map:
                        metadata[name_id_map[name_id]] = val

            # 2. Parse head table (Font Header)
            if 'head' in font:
                head = font['head']
                metadata['font_revision'] = getattr(head, 'fontRevision', None)
                metadata['units_per_em'] = getattr(head, 'unitsPerEm', None)
                metadata['bbox_xmin'] = getattr(head, 'xMin', None)
                metadata['bbox_ymin'] = getattr(head, 'yMin', None)
                metadata['bbox_xmax'] = getattr(head, 'xMax', None)
                metadata['bbox_ymax'] = getattr(head, 'yMax', None)
                
                created = getattr(head, 'created', None)
                if created is not None:
                    metadata['created_timestamp'] = self._mac_epoch_to_iso(created)
                modified = getattr(head, 'modified', None)
                if modified is not None:
                    metadata['modified_timestamp'] = self._mac_epoch_to_iso(modified)
                
                mac_style = getattr(head, 'macStyle', 0)
                metadata['mac_style_bold'] = bool(mac_style & 1)
                metadata['mac_style_italic'] = bool(mac_style & 2)

            # 3. Parse OS/2 table (OS/2 and Windows Metrics)
            if 'OS/2' in font:
                os2 = font['OS/2']
                metadata['weight_class'] = getattr(os2, 'usWeightClass', None)
                metadata['width_class'] = getattr(os2, 'usWidthClass', None)
                fs_type = getattr(os2, 'fsType', 0)
                metadata['embedding_permissions_flags'] = fs_type
                metadata['is_embeddable'] = not bool(fs_type & 0x0008)
                
                metadata['typo_ascender'] = getattr(os2, 'sTypoAscender', None)
                metadata['typo_descender'] = getattr(os2, 'sTypoDescender', None)
                metadata['typo_line_gap'] = getattr(os2, 'sTypoLineGap', None)
                metadata['win_ascent'] = getattr(os2, 'usWinAscent', None)
                metadata['win_descent'] = getattr(os2, 'usWinDescent', None)
                metadata['x_height'] = getattr(os2, 'sxHeight', None)
                metadata['cap_height'] = getattr(os2, 'sCapHeight', None)
                
                vendor_id = getattr(os2, 'achVendID', None)
                if vendor_id is not None:
                    if isinstance(vendor_id, bytes):
                        try:
                            metadata['vendor_id'] = vendor_id.decode('ascii', errors='ignore').strip()
                        except Exception:
                            pass
                    else:
                        metadata['vendor_id'] = str(vendor_id).strip()
                
                panose = getattr(os2, 'panose', None)
                if panose:
                    metadata['panose_family_type'] = getattr(panose, 'bFamilyType', None)
                    metadata['panose_serif_style'] = getattr(panose, 'bSerifStyle', None)
                    metadata['panose_weight'] = getattr(panose, 'bWeight', None)
                    metadata['panose_proportion'] = getattr(panose, 'bProportion', None)
                    metadata['panose_contrast'] = getattr(panose, 'bContrast', None)

            # 4. Parse post table (PostScript info)
            if 'post' in font:
                post = font['post']
                metadata['italic_angle'] = getattr(post, 'italicAngle', None)
                metadata['underline_position'] = getattr(post, 'underlinePosition', None)
                metadata['underline_thickness'] = getattr(post, 'underlineThickness', None)
                metadata['is_monospaced'] = bool(getattr(post, 'isFixedPitch', 0))

            # 5. Parse maxp table (Max profiles)
            if 'maxp' in font:
                maxp = font['maxp']
                metadata['num_glyphs'] = getattr(maxp, 'numGlyphs', None)

            # 7. Check Vietnamese support via cmap
            # Standard Vietnamese character codepoints including diacritics and Đ/đ
            vietnamese_codepoints = [
                0x0110, 0x0111, # Đ, đ
                0x01A0, 0x01A1, # Ơ, ơ
                0x01AF, 0x01B0, # Ư, ư
                0x1EA0, 0x1EA1, # Ạ, ạ
                0x1EA2, 0x1EA3, # Ả, ả
                0x1EA4, 0x1EA5, # Ấ, ấ
                0x1EAC, 0x1EAD, # Ậ, ậ
                0x1EB8, 0x1EB9, # Ẹ, ẹ
                0x1EBC, 0x1EBD, # Ẽ, ẽ
                0x1EC6, 0x1EC7, # Ệ, ệ
                0x1ED2, 0x1ED3, # Ồ, ồ
                0x1ED8, 0x1ED9, # Ộ, ộ
                0x1EF0, 0x1EF1, # Ự, ự
                0x1EF4, 0x1EF5, # Ỵ, ỵ
            ]
            cmap = font.getBestCmap()
            if cmap:
                metadata['supports_vietnamese'] = all(cp in cmap for cp in vietnamese_codepoints)
            else:
                metadata['supports_vietnamese'] = False

            # 8. Check if variable font and extract axes
            if 'fvar' in font:
                metadata['is_variable'] = True
                axes = []
                for axis in font['fvar'].axes:
                    axes.append({
                        'tag': str(axis.axisTag),
                        'min_value': float(axis.minValue),
                        'max_value': float(axis.maxValue),
                        'default_value': float(axis.defaultValue)
                    })
                metadata['variable_axes'] = axes
            else:
                metadata['is_variable'] = False
                metadata['variable_axes'] = []

            # 9. Extract OpenType typographic features (GSUB / GPOS)
            features = set()
            for table_tag in ('GSUB', 'GPOS'):
                if table_tag in font and hasattr(font[table_tag], 'table') and hasattr(font[table_tag].table, 'FeatureList'):
                    flist = font[table_tag].table.FeatureList
                    if flist and hasattr(flist, 'FeatureRecord'):
                        for record in flist.FeatureRecord:
                            if hasattr(record, 'FeatureTag'):
                                features.add(str(record.FeatureTag))
            metadata['open_type_features'] = sorted(list(features))

            # 10. Extract all table list present in font file
            metadata['tables_list'] = list(font.keys())

            # 6. Fill in general file metadata
            metadata['file_name'] = os.path.basename(file_path)
            metadata['file_path'] = os.path.abspath(file_path)
            metadata['file_size_bytes'] = os.path.getsize(file_path)
            metadata['format'] = os.path.splitext(file_path)[1][1:].upper()
            metadata['indexed_at'] = datetime.datetime.utcnow().isoformat() + "Z"
            
            # Ensure fallback values for critical fields
            if 'family' not in metadata:
                metadata['family'] = os.path.splitext(os.path.basename(file_path))[0]
            if 'full_name' not in metadata:
                metadata['full_name'] = metadata['family']
            if 'subfamily' not in metadata:
                metadata['subfamily'] = "Regular"
                
            return metadata
            
        except Exception as e:
            # Return basic file metadata with error if parsing failed
            return {
                'file_name': os.path.basename(file_path),
                'file_path': os.path.abspath(file_path),
                'file_size_bytes': os.path.getsize(file_path),
                'format': os.path.splitext(file_path)[1][1:].upper(),
                'indexed_at': datetime.datetime.utcnow().isoformat() + "Z",
                'error': str(e)
            }

    def index_file(self, file_path: str, index_name: str = "metadata") -> Dict[str, Any]:
        """Parse a font file and index its metadata into Elasticsearch."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Font file '{file_path}' does not exist.")
            
        metadata = self.parse_file(file_path)
        
        # Use a combination of font name and format to form unique doc ID
        clean_name = metadata.get('postscript_name') or metadata.get('full_name') or metadata.get('file_name')
        clean_name = "".join([c if c.isalnum() or c in "-_" else "_" for c in clean_name])
        doc_id = f"{clean_name}_{metadata.get('format', 'UNKNOWN').lower()}"
        
        response = self.es.index(index=index_name, id=doc_id, document=metadata)
        return response

    def index_directory(self, dir_path: str, index_name: str = "metadata") -> Dict[str, Any]:
        """Scan a directory for font files, parse metadata and index them."""
        if not os.path.isdir(dir_path):
            raise NotADirectoryError(f"Directory '{dir_path}' does not exist.")
            
        supported_extensions = {".ttf", ".otf", ".ttc", ".woff", ".woff2"}
        
        # Ensure index exists
        self.create_index(index_name)
        
        success_count = 0
        fail_count = 0
        errors = {}
        
        for root, _, files in os.walk(dir_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in supported_extensions:
                    file_path = os.path.join(root, file)
                    try:
                        self.index_file(file_path, index_name=index_name)
                        success_count += 1
                    except Exception as e:
                        fail_count += 1
                        errors[file] = str(e)
                        
        return {
            "total_processed": success_count + fail_count,
            "success_count": success_count,
            "fail_count": fail_count,
            "errors": errors
        }

    def search_fonts(self, query: str, index_name: str = "metadata", size: int = 20) -> List[Dict[str, Any]]:
        """Search indexed font metadata using simple query string search."""
        if not self.es.indices.exists(index=index_name):
            print(f"Index '{index_name}' does not exist yet.")
            return []
            
        search_body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": [
                        "family^3",
                        "full_name^3",
                        "postscript_name^2",
                        "designer",
                        "manufacturer",
                        "description"
                    ]
                }
            },
            "size": size
        }
        
        response = self.es.search(index=index_name, body=search_body)
        
        results = []
        for hit in response["hits"]["hits"]:
            results.append({
                "id": hit["_id"],
                "score": hit["_score"],
                "source": hit["_source"]
            })
        return results
