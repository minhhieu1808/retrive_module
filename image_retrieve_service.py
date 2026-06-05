import os
import base64
import mimetypes
import uuid
import datetime
import httpx
import numpy as np
import urllib3
from typing import Dict, Any, List, Optional
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

# Disable SSL verification warnings if user/pass is configured with self-signed certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ImageRetrieveService:
    """Service to handle generating image/text embeddings and retrieving images using Elasticsearch."""
    
    def __init__(
        self,
        es_url: Optional[str] = None,
        es_user: Optional[str] = None,
        es_password: Optional[str] = None
    ):
        load_dotenv(override=True)
        self.es_url = es_url or os.getenv("ELASTICSEARCH_URL", "http://171.232.252.198:9200").strip()
        
        # Force HTTP scheme
        if self.es_url.lower().startswith("https://"):
            self.es_url = "http://" + self.es_url[8:]
        elif not self.es_url.lower().startswith("http://"):
            self.es_url = "http://" + self.es_url
            
        self.es_user = es_user or os.getenv("ELASTICSEARCH_USER", "elastic").strip()
        self.es_password = es_password or os.getenv("ELASTICSEARCH_PASSWORD", "").strip()
        
        conn_params = {"hosts": [self.es_url]}
        if self.es_user and self.es_password:
            conn_params["basic_auth"] = (self.es_user, self.es_password)
            
        print(f"ImageRetrieveService: Connecting to Elasticsearch server at {self.es_url}...")
        self.es = Elasticsearch(**conn_params)
        
        # Test connection
        if self.es.ping():
            print("ImageRetrieveService: Successfully connected to Elasticsearch.")
        else:
            print("ImageRetrieveService: Connection to Elasticsearch returned ping False.")
            
        self._model = None
        
    def get_embedding_model(self):
        """Lazy load SentenceTransformer model if local execution is needed."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            model_name = os.getenv("EMBEDDING_MODEL", "Qwen/Qwen3-VL-Embedding-2B")
            try:
                print(f"Loading local embedding model: {model_name}...")
                self._model = SentenceTransformer(model_name)
            except Exception as e:
                print(f"Failed to load embedding model '{model_name}': {e}. Falling back to clip...")
                try:
                    self._model = SentenceTransformer("sentence-transformers/clip-ViT-B-32")
                except Exception as e2:
                    print(f"Failed to load fallback: {e2}. Using dummy mode.")
                    self._model = "dummy"
        return self._model

    def generate_embeddings(self, inputs: List[Dict[str, str]]) -> List[List[float]]:
        """Generate embeddings using the remote API or local fallback."""
        embedding_api_url = os.getenv("EMBEDDING_API_URL", "").strip()
        if embedding_api_url:
            print(f"ImageRetrieveService: Calling remote embedding API: {embedding_api_url}...")
            try:
                payload = {"inputs": inputs}
                with httpx.Client() as client:
                    response = client.post(embedding_api_url, json=payload, timeout=120.0)
                    if response.status_code == 200:
                        res_json = response.json()
                        embeddings = res_json.get("embeddings", [])
                        if embeddings:
                            return embeddings
                        else:
                            print("Warning: Remote API returned empty embeddings.")
                    else:
                        print(f"Warning: Remote API returned status {response.status_code}: {response.text}")
            except Exception as e:
                print(f"Error calling remote embedding API: {e}. Falling back to local/dummy...")

        # Local fallback
        model = self.get_embedding_model()
        
        # Parse inputs
        texts = []
        images = []
        for item in inputs:
            if item["type"] == "text":
                texts.append(item["data"])
            elif item["type"] == "image":
                img_data = item["data"]
                if "," in img_data:
                    img_data = img_data.split(",")[1]
                from PIL import Image
                import io
                img_bytes = base64.b64decode(img_data)
                img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                images.append(img)
                
        combined_text = " ".join(texts).strip()
        
        if model == "dummy":
            # Generate consistent mock vector of size 512 using seed
            seed = hash(combined_text) % (2**32)
            np.random.seed(seed)
            vec = np.random.randn(512)
            vec = vec / np.linalg.norm(vec)
            return [vec.tolist()]
            
        is_qwen = False
        if hasattr(model, "model_name_or_path"):
            is_qwen = "qwen" in str(model.model_name_or_path).lower()
            
        if is_qwen:
            if combined_text and images:
                input_dict = {"text": combined_text, "image": images[0]}
                emb = model.encode(input_dict)
            elif combined_text:
                emb = model.encode(combined_text)
            elif images:
                emb = model.encode(images[0])
            else:
                emb = model.encode("")
        else:
            # Fallback/CLIP: encode and average
            embs = []
            if combined_text:
                t_emb = model.encode(combined_text)
                embs.append(t_emb / np.linalg.norm(t_emb))
            if images:
                for img in images:
                    i_emb = model.encode(img)
                    embs.append(i_emb / np.linalg.norm(i_emb))
            if embs:
                combined = np.mean(embs, axis=0)
                combined = combined / np.linalg.norm(combined)
                emb = combined
            else:
                emb = np.zeros(512)
                
        if hasattr(emb, "tolist"):
            return [emb.tolist()]
        return [list(emb)]

    def create_index(self, index_name: str, vector_dim: int) -> bool:
        """Create Elasticsearch index with mappings appropriate for the vector dimension."""
        if self.es.indices.exists(index=index_name):
            print(f"ImageRetrieveService: Index '{index_name}' already exists.")
            return False
            
        print(f"ImageRetrieveService: Creating index '{index_name}' for dimension {vector_dim}...")
        
        properties = {
            "file_name": {"type": "keyword"},
            "file_path": {"type": "keyword"},
            "input_type": {"type": "keyword"},
            "timestamp": {"type": "date"},
            "vector_dim": {"type": "integer"},
            "description": {"type": "text"}
        }
        
        if vector_dim <= 1024:
            properties["embeddings"] = {
                "type": "dense_vector",
                "dims": vector_dim,
                "index": True,
                "similarity": "cosine"
            }
        else:
            # Large vector: split into 5 parts (up to 5120 dims, 1024 each to fit Elasticsearch index limits)
            for i in range(1, 6):
                properties[f"embeddings_part{i}"] = {
                    "type": "dense_vector",
                    "dims": 1024,
                    "index": True,
                    "similarity": "cosine"
                }
                properties[f"norm_part{i}"] = {"type": "float"}
            
        index_mapping = {"mappings": {"properties": properties}}
        self.es.indices.create(index=index_name, body=index_mapping)
        print(f"ImageRetrieveService: Index '{index_name}' created successfully.")
        return True

    def _prepare_vector_payload(self, vector: List[float]) -> Dict[str, Any]:
        """Normalize vector and split it if dimension > 2048."""
        dim = len(vector)
        arr = np.array(vector, dtype=np.float32)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
            
        payload = {"vector_dim": dim}
        
        if dim <= 1024:
            payload["embeddings"] = arr.tolist()
        else:
            # Split unit normalized vector into 5 parts of max 1024 dims each (0-1023, 1024-2047, 2048-3071, 3072-4095, 4096-5119)
            for i in range(1, 6):
                start = (i - 1) * 1024
                end = i * 1024
                part = np.zeros(1024, dtype=np.float32)
                part_len = min(dim - start, 1024)
                if part_len > 0:
                    part[0:part_len] = arr[start:start+part_len]
                
                n = float(np.linalg.norm(part))
                u = (part / n).tolist() if n > 0 else [0.0] * 1024
                
                payload[f"embeddings_part{i}"] = u
                payload[f"norm_part{i}"] = n
            
        return payload

    def index_image(self, file_path: str, index_name: str) -> Dict[str, Any]:
        """Generate embedding for an image and index it in Elasticsearch."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Image file '{file_path}' does not exist.")
            
        file_name = os.path.basename(file_path)
        
        # Open and resize image using Pillow to optimize payload size and avoid VRAM out-of-memory errors on the server
        from PIL import Image
        import io
        
        try:
            with Image.open(file_path) as img:
                # Resize image so that maximum dimension is 512px while maintaining aspect ratio
                img.thumbnail((512, 512))
                # Convert palette/RGBA to RGB for JPEG format compatibility
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                    
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                img_bytes = buffer.getvalue()
                
            encoded_string = base64.b64encode(img_bytes).decode('utf-8')
            mime_type = "image/jpeg"
        except Exception as resize_err:
            print(f"Warning: Failed to resize image {file_name} ({resize_err}). Falling back to raw file upload.")
            # Fallback to loading raw bytes if Pillow resize fails
            with open(file_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                mime_type = "image/jpeg"
            
        base64_data = f"data:{mime_type};base64,{encoded_string}"
        
        # Call API for embedding
        embeddings = self.generate_embeddings([{"type": "image", "data": base64_data}])
        if not embeddings:
            raise ValueError(f"Failed to generate embedding for image {file_name}.")
            
        vector = embeddings[0]
        dim = len(vector)
        
        # Ensure index exists
        self.create_index(index_name, dim)
        
        # Generate image description using vision LLM
        description = self.generate_image_description(base64_data)
        
        # Process vector payload
        doc_payload = self._prepare_vector_payload(vector)
        doc_payload.update({
            "file_name": file_name,
            "file_path": os.path.abspath(file_path),
            "input_type": "image",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "description": description
        })
        
        # Document ID based on filename hash
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, file_name))
        res = self.es.index(index=index_name, id=doc_id, document=doc_payload)
        return res

    def index_directory(self, dir_path: str, index_name: str) -> Dict[str, Any]:
        """Scan a directory for images and index all of them."""
        if not os.path.isdir(dir_path):
            raise NotADirectoryError(f"Directory '{dir_path}' does not exist.")
            
        valid_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif')
        image_files = [f for f in os.listdir(dir_path) if f.lower().endswith(valid_extensions)]
        
        success_count = 0
        fail_count = 0
        errors = {}
        
        for file in image_files:
            file_path = os.path.join(dir_path, file)
            try:
                self.index_image(file_path, index_name)
                success_count += 1
            except Exception as e:
                fail_count += 1
                errors[file] = str(e)
                print(f"Error indexing {file}: {e}")
                
        if success_count > 0:
            try:
                self.es.indices.refresh(index=index_name)
            except Exception as e:
                print(f"Error refreshing index '{index_name}': {e}")
                
        return {
            "total_processed": len(image_files),
                "success_count": success_count,
            "fail_count": fail_count,
            "errors": errors
        }

    def _search_by_vector(self, vector: List[float], index_name: str, top_k: int = 6) -> List[Dict[str, Any]]:
        """Perform vector similarity search on Elasticsearch using the provided embedding vector."""
        dim = len(vector)
        
        # Retrieve mapping to check fields
        mapping = self.es.indices.get_mapping(index=index_name)
        props = mapping[index_name]["mappings"]["properties"]
        
        # Check if index is mapped for split vectors or native
        is_split = "embeddings_part1" in props
        
        if not is_split:
            # Native vector query
            # We normalize the query vector
            arr = np.array(vector, dtype=np.float32)
            norm = np.linalg.norm(arr)
            if norm > 0:
                arr = arr / norm
            q_vector = arr.tolist()
            
            search_body = {
                "query": {
                    "script_score": {
                        "query": {"term": {"input_type": "image"}},
                        "script": {
                            "source": "cosineSimilarity(params.query_vector, 'embeddings') + 1.0",
                            "params": {"query_vector": q_vector}
                        }
                    }
                },
                "size": top_k
            }
        else:
            # Split vector query
            arr = np.array(vector, dtype=np.float32)
            norm = np.linalg.norm(arr)
            if norm > 0:
                arr = arr / norm
                
            params = {}
            source_lines = []
            
            for i in range(1, 6):
                start = (i - 1) * 1024
                part = np.zeros(1024, dtype=np.float32)
                part_len = min(dim - start, 1024)
                if part_len > 0:
                    part[0:part_len] = arr[start:start+part_len]
                    
                qn = float(np.linalg.norm(part))
                uq = (part / qn).tolist() if qn > 0 else [0.0] * 1024
                
                params[f"uq{i}"] = uq
                params[f"qn{i}"] = qn
                
                source_lines.append(f"""
                                if (doc['norm_part{i}'].size() > 0 && doc['norm_part{i}'].value > 0 && params.qn{i} > 0) {{
                                    score += cosineSimilarity(params.uq{i}, 'embeddings_part{i}') * doc['norm_part{i}'].value * params.qn{i};
                                }}""")
                
            painless_source = "double score = 0.0;" + "".join(source_lines) + " return score + 1.0;"
            
            search_body = {
                "query": {
                    "script_score": {
                        "query": {"term": {"input_type": "image"}},
                        "script": {
                            "source": painless_source,
                            "params": params
                        }
                    }
                },
                "size": top_k
            }
            
        res = self.es.search(index=index_name, body=search_body)
        
        results = []
        for hit in res["hits"]["hits"]:
            # Subtract 1.0 back to return the original cosine similarity score [-1.0, 1.0]
            similarity = hit["_score"] - 1.0
            
            # Map score to percentage similarity [0%, 100%]
            percent = max(0.0, min(100.0, ((similarity + 1.0) / 2.0) * 100.0))
            
            src = hit["_source"]
            results.append({
                "id": hit["_id"],
                "score": similarity,
                "percentage": round(percent, 2),
                "file_name": src.get("file_name"),
                "file_path": src.get("file_path"),
                "timestamp": src.get("timestamp"),
                "description": src.get("description", "")
            })
            
        return results

    def search_images(self, query_text: str, index_name: str, top_k: int = 6) -> List[Dict[str, Any]]:
        """Search images using a text query."""
        if not self.es.indices.exists(index=index_name):
            print(f"ImageRetrieveService: Index '{index_name}' does not exist.")
            return []
            
        # Get query embedding
        embeddings = self.generate_embeddings([{"type": "text", "data": query_text}])
        if not embeddings:
            print("ImageRetrieveService: Failed to generate embedding for query.")
            return []
            
        return self._search_by_vector(embeddings[0], index_name, top_k)

    def search_images_by_image(self, image_base64: str, index_name: str, top_k: int = 6) -> List[Dict[str, Any]]:
        """Search images using an uploaded query image."""
        if not self.es.indices.exists(index=index_name):
            print(f"ImageRetrieveService: Index '{index_name}' does not exist.")
            return []
            
        # Ensure correct prefix format for base64 payload if it's not present
        if not image_base64.startswith("data:"):
            # Fallback to jpeg mimetype guess
            image_base64 = "data:image/jpeg;base64," + image_base64
            
        # Get query embedding
        embeddings = self.generate_embeddings([{"type": "image", "data": image_base64}])
        if not embeddings:
            print("ImageRetrieveService: Failed to generate embedding for image query.")
            return []
            
        return self._search_by_vector(embeddings[0], index_name, top_k)

    def generate_image_description(self, image_base64: str) -> str:
        """Generate description for an image using the google/gemma-4-31b-it vision model."""
        llm_api_base = os.getenv("LLM_API_BASE", "http://localhost:4000/v1").strip()
        llm_api_key = os.getenv("LLM_API_KEY", "").strip()
        llm_model = os.getenv("LLM_MODEL", "google/gemma-4-31b-it").strip()
        
        if not llm_api_key:
            print("ImageRetrieveService: LLM_API_KEY is not configured. Skipping description generation.")
            return ""
            
        # Ensure base64 prefix
        if not image_base64.startswith("data:"):
            image_base64 = "data:image/jpeg;base64," + image_base64
            
        payload = {
            "model": llm_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Hãy mô tả ngắn gọn bức ảnh này bằng tiếng Việt để hỗ trợ tìm kiếm ảnh sau này. Viết khoảng 1-2 câu mô tả chi tiết các vật thể, màu sắc, phong cách."},
                        {"type": "image_url", "image_url": {"url": image_base64}}
                    ]
                }
            ],
            "temperature": 0.2
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {llm_api_key}"
        }
        
        endpoint = f"{llm_api_base.rstrip('/')}/chat/completions"
        
        print(f"ImageRetrieveService: Generating image description using model: {llm_model}...")
        try:
            # Call the LLM vision API (timeout 60s)
            with httpx.Client() as client:
                response = client.post(endpoint, json=payload, headers=headers, timeout=60.0)
                if response.status_code == 200:
                    data = response.json()
                    description = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    print(f"ImageRetrieveService: Generated description successfully.")
                    return description
                else:
                    print(f"Warning: Vision API returned status {response.status_code}: {response.text}")
        except Exception as e:
            print(f"Error generating image description: {e}")
            
        return ""
