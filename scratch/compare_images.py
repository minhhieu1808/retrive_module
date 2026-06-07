import os
import httpx
import numpy as np
import base64
from dotenv import load_dotenv

load_dotenv(override=True)
url = os.getenv("EMBEDDING_API_URL", "http://171.232.252.198:8686/embed").strip()

def get_image_emb(file_path):
    with open(file_path, "rb") as f:
        img_bytes = f.read()
    encoded = base64.b64encode(img_bytes).decode('utf-8')
    base64_data = f"data:image/jpeg;base64,{encoded}"
    
    payload = {"inputs": [{"type": "image", "data": base64_data}]}
    try:
        response = httpx.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            return np.array(response.json()["embeddings"][0])
        else:
            print(f"Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")
    return None

img_files = [
    "91.jpg",
    "1f26399e-08f2-429b-8ea7-5023b27ec899.jpg",
    "green-pedestal-podium-product-display-stand-empty-space-stage-studio-background-3d-rendering.jpg",
    "background-ghep-anh-21.jpg"
]

embs = {}
for name in img_files:
    path = os.path.join("image", name)
    embs[name] = get_image_emb(path)

output = []
for i in range(len(img_files)):
    for j in range(i, len(img_files)):
        name1 = img_files[i]
        name2 = img_files[j]
        v1 = embs[name1]
        v2 = embs[name2]
        if v1 is not None and v2 is not None:
            if i == j:
                output.append(f"{name1} norm: {np.linalg.norm(v1):.4f}")
            else:
                sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
                output.append(f"Similarity {name1} vs {name2}: {sim:.6f}")

with open("scratch/image_embedding_comparison.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print("Wrote comparison to scratch/image_embedding_comparison.txt")
