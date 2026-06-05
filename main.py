import os
import json
import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv

# Load env variables forcing overrides
load_dotenv(override=True)

app = FastAPI(
    title="Gemma Q&A API",
    description="FastAPI + Uvicorn server connecting to local LLM server using non-streaming JSON formats"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: str = os.getenv("LLM_MODEL", "google/gemma-4-31b-it")

@app.get("/api/config")
async def get_config():
    """Retrieve default settings for the client."""
    api_key = os.getenv("LLM_API_KEY", "sk-CIt4BMacaFUinEoL4unv-w")
    return {
        "api_key_configured": bool(api_key),
        "default_model": os.getenv("LLM_MODEL", "google/gemma-4-31b-it")
    }

async def generate_llm_response(messages: List[ChatMessage], model_name: str):
    """Call the local LLM server using standard JSON chat completions and yield the content field."""
    api_key = os.getenv("LLM_API_KEY", "sk-CIt4BMacaFUinEoL4unv-w")
    api_base = os.getenv("LLM_API_BASE", "http://localhost:4000/v1")
    
    # Map messages to OpenAI standard format
    formatted_messages = []
    for msg in messages:
        role = "assistant" if msg.role in ["model", "assistant"] else "user"
        formatted_messages.append({
            "role": role,
            "content": msg.content
        })
        
    headers = {
        "Content-Type": "application/json"
    }
    # Add authorization header if key is provided and valid
    if api_key and api_key.strip() and api_key != "your_authorization_token_here":
        headers["Authorization"] = f"Bearer {api_key.strip()}"
        
    # Payload matching the curl specifications (temperature: 0.7, no stream: True)
    payload = {
        "model": model_name,
        "messages": formatted_messages,
        "temperature": 0.7
    }
    
    endpoint = f"{api_base.rstrip('/')}/chat/completions"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=60.0
            )
            
            if response.status_code != 200:
                yield f"System Error from LLM server (HTTP {response.status_code}): {response.text}"
                return
                
            data = response.json()
            # Extract content from choices[0]["message"]["content"]
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content:
                yield content
            else:
                yield f"No content returned in response: {response.text}"
                
    except Exception as e:
        yield f"Error calling local LLM API: {str(e)}"

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """Endpoint called by frontend. Passes request to the generator."""
    if not request.messages:
        raise HTTPException(status_code=400, detail="Messages list cannot be empty")
        
    return StreamingResponse(
        generate_llm_response(request.messages, request.model),
        media_type="text/event-stream"
    )

# Mount static folder
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount image folder to serve indexed images
os.makedirs("image", exist_ok=True)
app.mount("/image", StaticFiles(directory="image"), name="image")

@app.get("/")
async def get_index():
    """Serve the main Chat UI."""
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Welcome to Gemma Q&A API. Please check if static/index.html is present."}

# --- Multimodal Embedding & Elasticsearch Integration ---

class InputItem(BaseModel):
    type: str # "text" or "image"
    data: str # text content or base64 data

class EmbeddingRequest(BaseModel):
    inputs: List[InputItem]

class EmbeddingResponse(BaseModel):
    embeddings: List[List[float]]

# Lazy load objects to optimize startup
_model = None
_es_client = None
_qdrant_client = None

def get_embedding_model():
    global _model
    if _model is None:
        import sys
        print("DEBUG INFO - sys.executable:", sys.executable)
        print("DEBUG INFO - sys.path:", sys.path)
        from sentence_transformers import SentenceTransformer
        model_name = os.getenv("EMBEDDING_MODEL", "Qwen/Qwen3-VL-Embedding-2B")
        try:
            print(f"Loading embedding model: {model_name}...")
            _model = SentenceTransformer(model_name)
        except Exception as e:
            print(f"Failed to load embedding model '{model_name}': {e}. Falling back to 'sentence-transformers/clip-ViT-B-32'...")
            try:
                _model = SentenceTransformer("sentence-transformers/clip-ViT-B-32")
            except Exception as e2:
                print(f"Failed to load fallback model: {e2}. Using 'dummy' mode.")
                _model = "dummy"
    return _model

def get_elasticsearch_client():
    global _es_client
    if _es_client is None:
        from elasticsearch import Elasticsearch
        import urllib3
        # Disable SSL verification warnings if user/pass is configured with self-signed certificate
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        es_url = os.getenv("ELASTICSEARCH_URL", "http://171.232.252.198:9200").strip()
        if es_url.lower().startswith("https://"):
            es_url = "http://" + es_url[8:]
        elif not es_url.lower().startswith("http://"):
            es_url = "http://" + es_url
            
        es_user = os.getenv("ELASTICSEARCH_USER", "elastic").strip()
        es_password = os.getenv("ELASTICSEARCH_PASSWORD", "").strip()
        
        conn_params = {"hosts": [es_url]}
        if es_user and es_password:
            conn_params["basic_auth"] = (es_user, es_password)
            
        print(f"Connecting to Elasticsearch server at {es_url}...")
        _es_client = Elasticsearch(**conn_params)
    return _es_client

def get_qdrant_client():
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient
        qdrant_url = os.getenv("QDRANT_URL", "").strip()
        qdrant_api_key = os.getenv("QDRANT_API_KEY", "").strip()
        
        if qdrant_url:
            if not qdrant_url.lower().startswith("http://") and not qdrant_url.lower().startswith("https://"):
                qdrant_url = "http://" + qdrant_url
            print(f"Connecting to Qdrant server at {qdrant_url}...")
            _qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key or None)
        else:
            print("QDRANT_URL is empty, using local in-memory Qdrant DB.")
            _qdrant_client = QdrantClient(":memory:")
    return _qdrant_client

def generate_multimodal_embedding(inputs: List[InputItem]) -> List[List[float]]:
    embedding_api_url = os.getenv("EMBEDDING_API_URL", "").strip()
    if embedding_api_url:
        print(f"Calling remote embedding API at: {embedding_api_url}...")
        try:
            payload = {
                "inputs": [
                    {
                        "type": item.type,
                        "data": item.data
                    } for item in inputs
                ]
            }
            with httpx.Client() as client:
                response = client.post(embedding_api_url, json=payload, timeout=120.0)
                if response.status_code == 200:
                    res_json = response.json()
                    embeddings = res_json.get("embeddings", [])
                    if embeddings:
                        return embeddings
                    else:
                        print("Warning: Remote API returned empty embeddings list.")
                else:
                    print(f"Warning: Remote API returned status code {response.status_code}: {response.text}")
        except Exception as e:
            print(f"Error calling remote embedding API: {e}. Falling back to local/dummy embedding...")

    model = get_embedding_model()
    
    # Parse text and images
    texts = []
    images = []
    for item in inputs:
        if item.type == "text":
            texts.append(item.data)
        elif item.type == "image":
            # Decode base64
            img_data = item.data
            if "," in img_data:
                img_data = img_data.split(",")[1]
            import base64
            from PIL import Image
            import io
            img_bytes = base64.b64decode(img_data)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            images.append(img)
            
    combined_text = " ".join(texts).strip()
    
    # Dummy mode
    if model == "dummy":
        import numpy as np
        # Generate consistent mock embedding of size 512 using seed
        seed = hash(combined_text) % (2**32)
        np.random.seed(seed)
        vec = np.random.randn(512)
        vec = vec / np.linalg.norm(vec)
        return [vec.tolist()]
        
    is_qwen = False
    if hasattr(model, "model_name_or_path"):
        is_qwen = "qwen" in str(model.model_name_or_path).lower()
        
    if is_qwen:
        # Qwen3-VL-Embedding accepts a dict for multimodal inputs
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
        # Fallback/CLIP: encode modalities separately and average
        import numpy as np
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

@app.post("/api/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(request: EmbeddingRequest):
    import datetime
    import uuid
    
    if not request.inputs:
        raise HTTPException(status_code=400, detail="Inputs list cannot be empty")
        
    try:
        # 1. Generate multimodal embeddings
        vectors = generate_multimodal_embedding(request.inputs)
        
        # 2. Store in Qdrant
        if vectors:
            q_client = get_qdrant_client()
            collection_name = os.getenv("QDRANT_COLLECTION", "vector_embeddings").strip()
            vector_dim = len(vectors[0])
            
            # Ensure collection exists
            try:
                collections = q_client.get_collections()
                exists = any(c.name == collection_name for c in collections.collections)
            except Exception:
                exists = False
                
            if not exists:
                from qdrant_client.models import Distance, VectorParams
                q_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=vector_dim, distance=Distance.COSINE)
                )
                
            # Index documents into Qdrant
            from qdrant_client.models import PointStruct
            for idx, vector in enumerate(vectors):
                input_type = "unknown"
                input_data = ""
                if idx < len(request.inputs):
                    input_type = request.inputs[idx].type
                    input_data = request.inputs[idx].data
                    if input_type == "image" and len(input_data) > 200:
                        input_data = input_data[:200] + "... (truncated)"
                else:
                    input_type = "multimodal_fallback"
                    input_data = " ".join([item.data for item in request.inputs if item.type == "text"]).strip()
                    
                doc_id = str(uuid.uuid4())
                q_client.upsert(
                    collection_name=collection_name,
                    points=[
                        PointStruct(
                            id=doc_id,
                            vector=vector,
                            payload={
                                "input_type": input_type,
                                "input_data": input_data,
                                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                            }
                        )
                    ]
                )
            
        return EmbeddingResponse(embeddings=vectors)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate and store embedding: {str(e)}")

# --- Image Retrieve API endpoints ---

@app.get("/api/images/stats")
async def get_image_stats_endpoint():
    """Retrieve collection status and item count from Qdrant."""
    try:
        from image_retrieve_service import ImageRetrieveService
        service = ImageRetrieveService()
        collection_name = os.getenv("QDRANT_COLLECTION", "vector_embeddings").strip()
        
        # Check if collection exists
        try:
            collections = service.qdrant_client.get_collections()
            exists = any(c.name == collection_name for c in collections.collections)
        except Exception:
            exists = False
            
        if not exists:
            return {
                "exists": False,
                "collection_name": collection_name,
                "points_count": 0,
                "status": "Not Created"
            }
            
        collection_info = service.qdrant_client.get_collection(collection_name)
        
        # Handle different structures of vector configurations in Qdrant
        vector_size = None
        if hasattr(collection_info.config.params, 'vectors'):
            vectors_param = collection_info.config.params.vectors
            if hasattr(vectors_param, 'size'):
                vector_size = vectors_param.size
            elif isinstance(vectors_param, dict) and len(vectors_param) > 0:
                first_key = list(vectors_param.keys())[0]
                first_vector = vectors_param[first_key]
                if hasattr(first_vector, 'size'):
                    vector_size = first_vector.size
                elif isinstance(first_vector, dict) and 'size' in first_vector:
                    vector_size = first_vector['size']
                
        return {
            "exists": True,
            "collection_name": collection_name,
            "points_count": collection_info.points_count,
            "status": str(collection_info.status),
            "vector_size": vector_size
        }
    except Exception as e:
        print(f"Error fetching stats: {e}")
        return {
            "exists": False,
            "error": str(e),
            "points_count": 0
        }

@app.post("/api/images/index")
async def index_images_endpoint():
    """Trigger indexing of the image directory."""
    try:
        from image_retrieve_service import ImageRetrieveService
        service = ImageRetrieveService()
        index_name = os.getenv("QDRANT_COLLECTION", "vector_embeddings").strip()
        result = service.index_directory("image", index_name)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to index images: {str(e)}")

@app.get("/api/images/search")
async def search_images_endpoint(query: str, limit: int = 6):
    """Retrieve images matching the query description."""
    if not query:
        raise HTTPException(status_code=400, detail="Query string parameter is required")
    try:
        from image_retrieve_service import ImageRetrieveService
        service = ImageRetrieveService()
        index_name = os.getenv("QDRANT_COLLECTION", "vector_embeddings").strip()
        results = service.search_images(query, index_name, top_k=limit)
        return {"results": results}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to search images: {str(e)}")

class ImageSearchRequest(BaseModel):
    image: str # Base64 representation (data:image/...)
    limit: int = 6

@app.post("/api/images/search-by-image")
async def search_images_by_image_endpoint(request: ImageSearchRequest):
    """Retrieve images matching the uploaded query image."""
    if not request.image:
        raise HTTPException(status_code=400, detail="Image base64 data is required")
    try:
        from image_retrieve_service import ImageRetrieveService
        service = ImageRetrieveService()
        index_name = os.getenv("QDRANT_COLLECTION", "vector_embeddings").strip()
        results = service.search_images_by_image(request.image, index_name, top_k=request.limit)
        return {"results": results}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to search images by image: {str(e)}")

@app.post("/api/images/search-by-image-file")
async def search_images_by_image_file_endpoint(file: UploadFile = File(...), limit: int = Form(6)):
    """Retrieve images matching the uploaded query image file (multipart/form-data)."""
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
            
        # Resize image using Pillow to optimize embedding payload size and avoid VRAM OOM
        from PIL import Image
        import io
        import base64
        
        try:
            with Image.open(io.BytesIO(content)) as img:
                img.thumbnail((512, 512))
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                img_bytes = buffer.getvalue()
            encoded_string = base64.b64encode(img_bytes).decode('utf-8')
            mime_type = "image/jpeg"
        except Exception as resize_err:
            print(f"Warning: Failed to resize query image ({resize_err}). Using raw file upload.")
            encoded_string = base64.b64encode(content).decode('utf-8')
            mime_type = file.content_type or "image/jpeg"
            
        base64_data = f"data:{mime_type};base64,{encoded_string}"
        
        from image_retrieve_service import ImageRetrieveService
        service = ImageRetrieveService()
        index_name = os.getenv("QDRANT_COLLECTION", "vector_embeddings").strip()
        results = service.search_images_by_image(base64_data, index_name, top_k=limit)
        return {"results": results}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to search images by file: {str(e)}")

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting server on http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=True)
