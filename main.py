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

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting server on http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=True)
