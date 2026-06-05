import os
from qdrant_client import QdrantClient
from dotenv import load_dotenv

load_dotenv(override=True)
qdrant_url = os.getenv("QDRANT_URL", "http://171.232.252.198:6333").strip()
collection_name = os.getenv("QDRANT_COLLECTION", "vector_embeddings").strip()

print(f"Connecting to Qdrant at {qdrant_url}...")
client = QdrantClient(url=qdrant_url)

try:
    collections = client.get_collections()
    print("Available collections:")
    for c in collections.collections:
        print(f" - {c.name}")
        
    info = client.get_collection(collection_name)
    print(f"\nCollection {collection_name} info:")
    print(f" - status: {info.status}")
    print(f" - points_count: {info.points_count}")
    print(f" - vectors_config: {info.config.params.vectors}")
    
    # Scroll points
    points, _ = client.scroll(
        collection_name=collection_name,
        limit=10,
        with_payload=True,
        with_vectors=False
    )
    print(f"\nScroll results (up to 10 points):")
    for p in points:
        print(f"ID: {p.id}")
        print(f"Payload: {p.payload}")
        print("-" * 40)
        
except Exception as e:
    print(f"Error: {e}")
