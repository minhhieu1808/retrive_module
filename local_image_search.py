import os
import sys
import numpy as np
from pathlib import Path
from PIL import Image

# Add workspace path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from es_image_service import CLIPEmbedder

def cosine_similarity(v1, v2):
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return float(dot_product / (norm_v1 * norm_v2))

def search_locally(query_text: str, images_dir: str = "images"):
    dir_path = Path(images_dir)
    if not dir_path.is_dir():
        print(f"Error: Directory '{images_dir}' not found.")
        return

    print("Loading local CLIP model (this may take a few seconds)...")
    try:
        embedder = CLIPEmbedder()
    except Exception as e:
        print(f"Error loading model: {e}")
        return

    # Find images
    extensions = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
    image_paths = []
    for ext in extensions:
        image_paths.extend(dir_path.glob(f"*{ext}"))
        image_paths.extend(dir_path.glob(f"*{ext.upper()}"))

    if not image_paths:
        print(f"No images found in '{images_dir}'")
        return

    print(f"Generating embeddings for {len(image_paths)} images...")
    image_embeddings = []
    valid_paths = []
    
    for path in image_paths:
        try:
            with Image.open(path) as img:
                emb = embedder.get_image_embedding(img)
                image_embeddings.append(emb)
                valid_paths.append(path)
        except Exception as e:
            print(f"Failed to process {path.name}: {e}")

    if not image_embeddings:
        print("No valid image embeddings generated.")
        return

    print(f"\nGenerating text embedding for query: '{query_text}'...")
    query_vector = embedder.get_text_embedding(query_text)

    # Compute similarities
    scores = []
    for i, img_emb in enumerate(image_embeddings):
        score = cosine_similarity(query_vector, img_emb)
        scores.append((score, valid_paths[i]))

    # Sort by similarity score descending
    scores.sort(key=lambda x: x[0], reverse=True)

    print("\nLocal Semantic Search Results:")
    print("-" * 80)
    print(f"{'No.':<4} | {'Similarity Score':<18} | {'Filename':<30} | {'Path'}")
    print("-" * 90)
    for idx, (score, path) in enumerate(scores, start=1):
        print(f"{idx:<4} | {score:<18.4f} | {path.name:<30} | {path.resolve()}")
    print("-" * 90)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py local_image_search.py \"your text query\"")
        query = "a photo of a person or background"
    else:
        query = sys.argv[1]
        
    search_locally(query)
