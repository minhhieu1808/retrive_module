import os
import io
from typing import Union, List, Dict, Any
from elasticsearch import Elasticsearch
from PIL import Image

class GeminiEmbedder:
    """Multimodal embedding generator using Google Gemini's gemini-embedding-2."""
    def __init__(self, api_key: str = None):
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise ImportError(
                "google-genai is not installed. Run `pip install google-genai` to use Gemini embeddings."
            )
        
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set in `.env` or passed to GeminiEmbedder."
            )
            
        self.client = genai.Client(api_key=api_key)
        self.types = types

    def get_image_embedding(self, image: Image.Image) -> List[float]:
        """Convert PIL Image to bytes and generate multimodal embedding."""
        img_byte_arr = io.BytesIO()
        # Save image to JPEG bytes
        image.save(img_byte_arr, format='JPEG')
        img_bytes = img_byte_arr.getvalue()
        
        response = self.client.models.embed_content(
            model="gemini-embedding-2",
            contents=[
                self.types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
            ]
        )
        return response.embeddings[0].values

    def get_text_embedding(self, text: str) -> List[float]:
        """Generate embedding from a text string."""
        response = self.client.models.embed_content(
            model="gemini-embedding-2",
            contents=text
        )
        return response.embeddings[0].values


class CLIPEmbedder:
    """Local embedding generator using OpenAI's CLIP model."""
    def __init__(self):
        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor
        except ImportError:
            raise ImportError(
                "PyTorch or Transformers is not installed. "
                "Run `pip install torch transformers` to use local CLIP embeddings."
            )
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        # Use openai/clip-vit-base-patch32 (yields 512 dimensions)
        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(self.device)
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

    def get_image_embedding(self, image: Image.Image) -> List[float]:
        """Index image and generate 512-dim embedding."""
        import torch
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            embeddings = self.model.get_image_features(**inputs)
            # Handle new transformers returning BaseModelOutputWithPooling
            if hasattr(embeddings, "pooler_output"):
                embeddings = embeddings.pooler_output
            elif isinstance(embeddings, dict) and "pooler_output" in embeddings:
                embeddings = embeddings["pooler_output"]
        return embeddings.squeeze().tolist()

    def get_text_embedding(self, text: str) -> List[float]:
        """Generate 512-dim text embedding for cross-modal search."""
        import torch
        inputs = self.processor(text=[text], return_tensors="pt", padding=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            embeddings = self.model.get_text_features(**inputs)
            # Handle new transformers returning BaseModelOutputWithPooling
            if hasattr(embeddings, "pooler_output"):
                embeddings = embeddings.pooler_output
            elif isinstance(embeddings, dict) and "pooler_output" in embeddings:
                embeddings = embeddings["pooler_output"]
        return embeddings.squeeze().tolist()


class ElasticsearchImageService:
    """Service to handle indexing and k-NN semantic search on images inside Elasticsearch."""
    def __init__(self, provider: str = "gemini", es_url: str = None, gemini_api_key: str = None):
        self.provider = provider.lower()
        
        # Load Elasticsearch configurations
        es_url = es_url or os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
        es_user = os.getenv("ELASTICSEARCH_USER")
        es_password = os.getenv("ELASTICSEARCH_PASSWORD")
        es_api_key = os.getenv("ELASTICSEARCH_API_KEY")
        
        conn_params = {"hosts": [es_url]}
        
        # Only add credentials if they are configured and not empty strings
        if es_api_key and es_api_key.strip():
            conn_params["api_key"] = es_api_key
        elif es_user and es_user.strip() and es_password and es_password.strip():
            conn_params["basic_auth"] = (es_user, es_password)
            
        # Support bypassing SSL warnings for self-signed certificates on local Dev environments
        if es_url.startswith("https"):
            conn_params["verify_certs"] = False
            conn_params["ssl_show_warn"] = False
            
        self.es = Elasticsearch(**conn_params)
        
        # Instantiate correct embedder based on choice
        if self.provider == "gemini":
            self.embedder = GeminiEmbedder(api_key=gemini_api_key)
            self.vector_dims = 3072
        elif self.provider == "clip":
            self.embedder = CLIPEmbedder()
            self.vector_dims = 512
        else:
            raise ValueError("Unsupported provider. Choose 'gemini' or 'clip'.")

    def create_index(self, index_name: str = "image_embedding") -> bool:
        """Creates an index with dense_vector field optimized for k-NN search."""
        index_mapping = {
            "mappings": {
                "properties": {
                    "image_path": {"type": "keyword"},
                    "metadata": {"type": "object"},
                    "image_vector": {
                        "type": "dense_vector",
                        "dims": self.vector_dims,
                        "index": True,
                        "similarity": "cosine"
                    }
                }
            }
        }
        
        if self.es.indices.exists(index=index_name):
            print(f"Index '{index_name}' already exists. Skipping creation.")
            return False
            
        self.es.indices.create(index=index_name, body=index_mapping)
        print(f"Index '{index_name}' created successfully with {self.vector_dims}-dim vector mapping.")
        return True

    def index_image(self, doc_id: str, image_path_or_bytes: Union[str, bytes], index_name: str = "image_embedding", metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generates embedding vector of the image and indexes it to Elasticsearch."""
        if isinstance(image_path_or_bytes, bytes):
            image = Image.open(io.BytesIO(image_path_or_bytes))
            path_label = f"bytes_input_{doc_id}"
        else:
            image = Image.open(image_path_or_bytes)
            path_label = image_path_or_bytes
            
        # Get embedding vector
        vector = self.embedder.get_image_embedding(image)
        
        doc = {
            "image_path": path_label,
            "metadata": metadata or {},
            "image_vector": vector
        }
        
        response = self.es.index(index=index_name, id=doc_id, document=doc)
        return response

    def search_by_image(self, image_path_or_bytes: Union[str, bytes], index_name: str = "image_embedding", top_k: int = 5) -> List[Dict[str, Any]]:
        """Searches similar images by query image."""
        if isinstance(image_path_or_bytes, bytes):
            image = Image.open(io.BytesIO(image_path_or_bytes))
        else:
            image = Image.open(image_path_or_bytes)
            
        vector = self.embedder.get_image_embedding(image)
        return self._knn_search(index_name, vector, top_k)

    def search_by_text(self, query_text: str, index_name: str = "image_embedding", top_k: int = 5) -> List[Dict[str, Any]]:
        """Cross-modal search (Text-to-Image) using natural language query."""
        vector = self.embedder.get_text_embedding(query_text)
        return self._knn_search(index_name, vector, top_k)

    def _knn_search(self, index_name: str, query_vector: List[float], top_k: int) -> List[Dict[str, Any]]:
        """Internal helper to execute a k-NN dense vector search."""
        knn_query = {
            "field": "image_vector",
            "query_vector": query_vector,
            "k": top_k,
            "num_candidates": max(100, top_k * 10)
        }
        
        response = self.es.search(
            index=index_name,
            knn=knn_query,
            source=["image_path", "metadata"]  # Omit the high-dim vector in return payload for speed
        )
        
        results = []
        for hit in response["hits"]["hits"]:
            results.append({
                "id": hit["_id"],
                "score": hit["_score"],
                "image_path": hit["_source"].get("image_path"),
                "metadata": hit["_source"].get("metadata", {})
            })
        return results
