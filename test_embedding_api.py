import os
import httpx
import json
import base64
import time
import mimetypes
import uuid
import datetime
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# Load environment variables
load_dotenv(override=True)

def run_test():
    # Target the local FastAPI server endpoint
    url = "http://127.0.0.1:8000/api/embeddings"
    image_dir = "image"
    
    # 1. Initialize Qdrant Client (defaulting collection to "vector_embedding")
    qdrant_url = os.getenv("QDRANT_URL", "").strip()
    qdrant_api_key = os.getenv("QDRANT_API_KEY", "").strip()
    collection_name = os.getenv("QDRANT_COLLECTION", "vector_embedding").strip()
    
    print("--- Qdrant Connection Setup ---")
    try:
        if qdrant_url:
            print(f"Connecting to Qdrant server at {qdrant_url}...")
            q_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key or None, timeout=5.0)
            # Test connection
            q_client.get_collections()
            print("Successfully connected to remote Qdrant server.")
        else:
            raise ValueError("QDRANT_URL not set in environment.")
    except Exception as e:
        print(f"Remote Qdrant connection failed: {e}")
        print("Falling back to local persistent Qdrant database (saved in './qdrant_db')...")
        q_client = QdrantClient(path="./qdrant_db")
        
    if not os.path.exists(image_dir):
        print(f"\nError: Directory '{image_dir}' does not exist.")
        return
        
    # Get all files in the image directory
    valid_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif')
    image_files = [f for f in os.listdir(image_dir) if f.lower().endswith(valid_extensions)]
    
    if not image_files:
        print(f"\nNo valid image files found in '{image_dir}' directory.")
        return
        
    print(f"\nFound {len(image_files)} image(s) to process in '{image_dir}': {image_files}\n")
    
    for img_name in image_files:
        img_path = os.path.join(image_dir, img_name)
        print(f"Processing: {img_name}")
        
        try:
            # Read file and encode to base64
            with open(img_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                
            # Determine mime type
            mime_type, _ = mimetypes.guess_type(img_path)
            if not mime_type:
                mime_type = "image/jpeg" # Default fallback
                
            base64_data = f"data:{mime_type};base64,{encoded_string}"
            text_prompt = "Hello world from Qwen3-VL!"
            
            payload = {
                "inputs": [
                    {
                        "type": "text",
                        "data": text_prompt
                    },
                    {
                        "type": "image",
                        "data": base64_data
                    }
                ]
            }
            
            print(f"  -> Sending POST request to {url}...")
            payload_str = json.dumps(payload)
            print(f"  -> Payload Preview: {payload_str[:150]}...")
            
            start_time = time.time()
            response = httpx.post(url, json=payload, timeout=120.0)
            elapsed = time.time() - start_time
            
            print(f"  -> HTTP Status Code: {response.status_code} ({elapsed:.2f}s)")
            
            if response.status_code == 200:
                res_json = response.json()
                embeddings = res_json.get("embeddings", [])
                
                if embeddings:
                    vector_dim = len(embeddings[0])
                    print(f"  -> Successfully generated {len(embeddings)} embedding(s) (dim={vector_dim}).")
                    
                    # Ensure the Qdrant collection exists
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
                        print(f"  -> Collection '{collection_name}' does not exist. Creating collection...")
                        q_client.create_collection(
                            collection_name=collection_name,
                            vectors_config={
                                "embeddings": VectorParams(size=vector_dim, distance=Distance.COSINE)
                            },
                        )
                        print(f"  -> Collection '{collection_name}' created.")
                    
                    # Prepare points for Qdrant
                    points_to_upsert = []
                    for idx, emb_vector in enumerate(embeddings):
                        input_item = payload["inputs"][idx]
                        point_id = str(uuid.uuid4())
                        
                        # Limit payload size for images
                        input_data_preview = input_item["data"]
                        if input_item["type"] == "image" and len(input_data_preview) > 200:
                            input_data_preview = input_data_preview[:200] + "... (truncated)"
                            
                        point_payload = {
                            "file_name": img_name,
                            "file_path": img_path,
                            "input_type": input_item["type"],
                            "input_data": input_data_preview,
                            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                        }
                        
                        points_to_upsert.append(
                            PointStruct(
                                id=point_id,
                                vector={"embeddings": emb_vector},
                                payload=point_payload
                            )
                        )
                    
                    print(f"  -> Upserting {len(points_to_upsert)} vector(s) to Qdrant...")
                    q_client.upsert(
                        collection_name=collection_name,
                        points=points_to_upsert
                    )
                    print(f"  -> Upsert SUCCESS for all vectors of {img_name}!")
                else:
                    print("  -> Error: Embedding API did not return any embeddings.")
                    print(f"  -> Response: {response.text}")
            else:
                print(f"  -> Error: API response status {response.status_code}")
                print(response.text)
                
        except Exception as e:
            print(f"  -> An error occurred while processing {img_name}: {e}")
            
        print("-" * 60)
        
    # Check total points in the collection after finished
    try:
        info = q_client.get_collection(collection_name)
        print(f"\nFinal Qdrant Status: Collection '{collection_name}' has {info.points_count} point(s).")
    except Exception as e:
        print(f"\nCould not fetch collection status: {e}")

if __name__ == "__main__":
    run_test()
