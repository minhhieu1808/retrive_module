import os
import httpx
import numpy as np
from dotenv import load_dotenv

load_dotenv(override=True)
url = os.getenv("EMBEDDING_API_URL", "http://171.232.252.198:8686/embed").strip()

print(f"Calling remote embedding API at: {url}")

def get_emb(text):
    payload = {"inputs": [{"type": "text", "data": text}]}
    try:
        response = httpx.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return np.array(response.json()["embeddings"][0])
        else:
            print(f"Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")
    return None

v1 = get_emb("mau trang")
v2 = get_emb("mau xanh")
v3 = get_emb("mot con huou")

if v1 is not None and v2 is not None and v3 is not None:
    print(f"Vector dim: {v1.shape}")
    print(f"v1 norm: {np.linalg.norm(v1)}")
    print(f"v2 norm: {np.linalg.norm(v2)}")
    print(f"v3 norm: {np.linalg.norm(v3)}")
    
    # Cosine similarities
    cos12 = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    cos13 = np.dot(v1, v3) / (np.linalg.norm(v1) * np.linalg.norm(v3))
    cos23 = np.dot(v2, v3) / (np.linalg.norm(v2) * np.linalg.norm(v3))
    
    print(f"Cosine similarity between v1 and v2: {cos12}")
    print(f"Cosine similarity between v1 and v3: {cos13}")
    print(f"Cosine similarity between v2 and v3: {cos23}")
    
    # Check if they are exactly the same
    print(f"Are v1 and v2 identical? {np.allclose(v1, v2)}")
else:
    print("Failed to fetch vectors.")
