import os
import json
from qdrant_client import QdrantClient
from dotenv import load_dotenv

load_dotenv(override=True)
qdrant_url = os.getenv("QDRANT_URL", "http://171.232.252.198:6333").strip()
collection_name = os.getenv("QDRANT_COLLECTION", "vector_embeddings").strip()

client = QdrantClient(url=qdrant_url)

try:
    info = client.get_collection(collection_name)
    points, _ = client.scroll(
        collection_name=collection_name,
        limit=10,
        with_payload=True,
        with_vectors=False
    )
    
    output = []
    output.append(f"Collection: {collection_name}")
    output.append(f"Points count: {info.points_count}")
    output.append("-" * 40)
    for p in points:
        output.append(f"ID: {p.id}")
        output.append(f"File Name: {p.payload.get('file_name')}")
        output.append(f"File Path: {p.payload.get('file_path')}")
        output.append(f"Input Type: {p.payload.get('input_type')}")
        output.append(f"Description: {p.payload.get('description')}")
        output.append("-" * 40)
        
    with open("scratch/inspect_qdrant_utf8.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output))
    print("Successfully wrote inspect results in UTF-8 to scratch/inspect_qdrant_utf8.txt")
except Exception as e:
    print(f"Error: {e}")
