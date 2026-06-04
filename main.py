import os
import json
import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
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

@app.get("/")
async def get_index():
    """Serve the main Chat UI."""
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Welcome to Gemma Q&A API. Please check if static/index.html is present."}

# --- Multimodal Embedding & Qdrant Integration ---

class InputItem(BaseModel):
    type: str # "text" or "image"
    data: str # text content or base64 data

class EmbeddingRequest(BaseModel):
    inputs: List[InputItem]

class EmbeddingResponse(BaseModel):
    embeddings: List[List[float]]

# Lazy load objects to optimize startup
_model = None
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

def get_qdrant_client():
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient
        qdrant_url = os.getenv("QDRANT_URL", "").strip()
        qdrant_api_key = os.getenv("QDRANT_API_KEY", "").strip()
        
        if qdrant_url:
            print(f"Connecting to Qdrant server at {qdrant_url}...")
            _qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key or None)
        else:
            print("QDRANT_URL not configured. Using local in-memory Qdrant client...")
            _qdrant_client = QdrantClient(location=":memory:")
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
            collection_name = os.getenv("QDRANT_COLLECTION", "vector_embedding").strip()
            vector_dim = len(vectors[0])
            
            # Ensure collection exists
            try:
                exists = q_client.collection_exists(collection_name)
            except Exception:
                exists = False
                try:
                    q_client.get_collection(collection_name)
                    exists = True
                except Exception:
                    pass
                    
            if not exists:
                from qdrant_client.models import Distance, VectorParams
                q_client.create_collection(
                    collection_name=collection_name,
                    vectors_config={
                        "embeddings": VectorParams(size=vector_dim, distance=Distance.COSINE)
                    },
                )
                
            # Index points into Qdrant
            from qdrant_client.models import PointStruct
            points = []
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
                    
                point_id = str(uuid.uuid4())
                points.append(
                    PointStruct(
                        id=point_id,
                        vector={"embeddings": vector},
                        payload={
                            "input_type": input_type,
                            "input_data": input_data,
                            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                        }
                    )
                )
                
            q_client.upsert(
                collection_name=collection_name,
                points=points
            )
            
        return EmbeddingResponse(embeddings=vectors)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate and store embedding: {str(e)}")

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting server on http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=True)
