import os
import base64
import mimetypes
import uuid
import datetime
import httpx
import numpy as np
import urllib3
from typing import Dict, Any, List, Optional
from qdrant_client import QdrantClient
from dotenv import load_dotenv

# Disable SSL verification warnings if user/pass is configured with self-signed certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ImageRetrieveService:
    """Service to handle generating image/text embeddings and retrieving images using Qdrant."""
    
    def __init__(
        self,
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None,
        es_url: Optional[str] = None,      # Kept for compatibility
        es_user: Optional[str] = None,     # Kept for compatibility
        es_password: Optional[str] = None  # Kept for compatibility
    ):
        load_dotenv(override=True)
        self.qdrant_url = qdrant_url or os.getenv("QDRANT_URL", "").strip()
        self.qdrant_api_key = qdrant_api_key or os.getenv("QDRANT_API_KEY", "").strip()
        self.collection_name = os.getenv("QDRANT_COLLECTION", "vector_embeddings").strip()
        
        if self.qdrant_url:
            if not self.qdrant_url.lower().startswith("http://") and not self.qdrant_url.lower().startswith("https://"):
                self.qdrant_url = "http://" + self.qdrant_url
            print(f"ImageRetrieveService: Connecting to Qdrant server at {self.qdrant_url}...")
            self.qdrant_client = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_api_key or None)
        else:
            print("ImageRetrieveService: QDRANT_URL is empty, using local in-memory Qdrant DB.")
            self.qdrant_client = QdrantClient(":memory:")
            
        # Test connection
        try:
            self.qdrant_client.get_collections()
            print("ImageRetrieveService: Successfully connected to Qdrant.")
        except Exception as e:
            print(f"ImageRetrieveService: Connection to Qdrant failed: {e}")
            
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
        """Create Qdrant collection appropriate for the vector dimension."""
        try:
            collections = self.qdrant_client.get_collections()
            exists = any(c.name == index_name for c in collections.collections)
            if exists:
                print(f"ImageRetrieveService: Collection '{index_name}' already exists.")
                return False
        except Exception as e:
            print(f"ImageRetrieveService: Error checking collection existence: {e}")
            
        print(f"ImageRetrieveService: Creating Qdrant collection '{index_name}' for dimension {vector_dim}...")
        try:
            from qdrant_client.models import Distance, VectorParams
            self.qdrant_client.create_collection(
                collection_name=index_name,
                vectors_config=VectorParams(size=vector_dim, distance=Distance.COSINE)
            )
            print(f"ImageRetrieveService: Collection '{index_name}' created successfully.")
            return True
        except Exception as e:
            print(f"ImageRetrieveService: Failed to create collection '{index_name}': {e}")
            return False

    def index_image(self, file_path: str, index_name: str) -> Dict[str, Any]:
        """Generate embedding for an image and index it in Qdrant."""
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
        
        # Ensure collection exists
        self.create_index(index_name, dim)
        
        # Determine vector payload format dynamically (named vs unnamed vectors)
        try:
            collection_info = self.qdrant_client.get_collection(index_name)
            vectors_config = collection_info.config.params.vectors
            if isinstance(vectors_config, dict):
                vector_name = list(vectors_config.keys())[0]
                qdrant_vector = {vector_name: vector}
            else:
                qdrant_vector = vector
        except Exception as e:
            print(f"ImageRetrieveService: Error getting collection configuration: {e}")
            qdrant_vector = vector
            
        # Generate image description using vision LLM
        description = self.generate_image_description(base64_data)
        
        # Document ID based on filename hash
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, file_name))
        
        from qdrant_client.models import PointStruct
        res = self.qdrant_client.upsert(
            collection_name=index_name,
            points=[
                PointStruct(
                    id=doc_id,
                    vector=qdrant_vector,
                    payload={
                        "file_name": file_name,
                        "file_path": os.path.abspath(file_path),
                        "input_type": "image",
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "description": description
                    }
                )
            ]
        )
        return {"result": "created", "_id": doc_id, "status": str(res.status)}


    def index_directory(self, dir_path: str, index_name: str) -> Dict[str, Any]:
        """Scan a directory for images and index all of them into Qdrant."""
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
                
        return {
            "total_processed": len(image_files),
            "success_count": success_count,
            "fail_count": fail_count,
            "errors": errors
        }

    def _search_by_vector(self, vector: List[float], index_name: str, top_k: int = 6) -> List[Dict[str, Any]]:
        """Perform vector similarity search on Qdrant using the provided embedding vector."""
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            # Determine vector format dynamically (named vs unnamed vectors)
            vector_name = None
            try:
                collection_info = self.qdrant_client.get_collection(index_name)
                vectors_config = collection_info.config.params.vectors
                if isinstance(vectors_config, dict):
                    vector_name = list(vectors_config.keys())[0]
            except Exception as e:
                print(f"ImageRetrieveService: Error getting collection configuration for search: {e}")
                
            query_res = self.qdrant_client.query_points(
                collection_name=index_name,
                query=vector,
                using=vector_name,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="input_type",
                            match=MatchValue(value="image")
                        )
                    ]
                ),
                limit=top_k
            )
            
            results = []
            for hit in query_res.points:
                similarity = hit.score
                
                # Map score to percentage similarity [0%, 100%]
                percent = max(0.0, min(100.0, ((similarity + 1.0) / 2.0) * 100.0))
                
                payload = hit.payload or {}
                results.append({
                    "id": hit.id,
                    "score": similarity,
                    "percentage": round(percent, 2),
                    "file_name": payload.get("file_name"),
                    "file_path": payload.get("file_path"),
                    "timestamp": payload.get("timestamp"),
                    "description": payload.get("description", "")
                })
            return results
        except Exception as e:
            print(f"ImageRetrieveService: Error searching by vector in Qdrant: {e}")
            return []

    def search_images(self, query_text: str, index_name: str, top_k: int = 6) -> List[Dict[str, Any]]:
        """Search images using a text query."""
        try:
            collections = self.qdrant_client.get_collections()
            exists = any(c.name == index_name for c in collections.collections)
            if not exists:
                print(f"ImageRetrieveService: Collection '{index_name}' does not exist.")
                return []
        except Exception as e:
            print(f"ImageRetrieveService: Error checking collection: {e}")
            return []
            
        # Get query embedding
        embeddings = self.generate_embeddings([{"type": "text", "data": query_text}])
        if not embeddings:
            print("ImageRetrieveService: Failed to generate embedding for query.")
            return []
            
        return self._search_by_vector(embeddings[0], index_name, top_k)

    def search_images_by_image(self, image_base64: str, index_name: str, top_k: int = 6) -> List[Dict[str, Any]]:
        """Search images using an uploaded query image."""
        try:
            collections = self.qdrant_client.get_collections()
            exists = any(c.name == index_name for c in collections.collections)
            if not exists:
                print(f"ImageRetrieveService: Collection '{index_name}' does not exist.")
                return []
        except Exception as e:
            print(f"ImageRetrieveService: Error checking collection: {e}")
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
