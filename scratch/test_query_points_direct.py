import os
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from dotenv import load_dotenv

def test_query_points():
    load_dotenv(override=True)
    
    qdrant_url = os.getenv("QDRANT_URL", "http://171.232.252.198:6333").strip()
    collection_name = os.getenv("QDRANT_COLLECTION", "vector_embeddings").strip()
    
    print(f"Connecting to Qdrant at {qdrant_url}...")
    client = QdrantClient(url=qdrant_url)
    
    # Check collection config
    collection_info = client.get_collection(collection_name)
    vectors_config = collection_info.config.params.vectors
    vector_name = None
    if isinstance(vectors_config, dict):
        vector_name = list(vectors_config.keys())[0]
        
    print(f"Collection: {collection_name}")
    print(f"Vector Name: {vector_name}")
    
    # We query with a dummy vector of 0s of length 5120
    query_vector = [0.0] * 5120
    
    print("\nRunning query_points search...")
    res = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        using=vector_name,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="input_type",
                    match=MatchValue(value="image")
                )
            ]
        ),
        limit=5
    )
    
    print(f"Found {len(res.points)} points:")
    for i, p in enumerate(res.points):
        print(f" {i+1}. ID: {p.id}")
        print(f"    Score: {p.score}")
        print(f"    File: {p.payload.get('file_name')}")
        desc = p.payload.get('description', '')
        # Encode with utf-8 or print repr to avoid terminal charmap error
        print(f"    Description: {repr(desc)}")

if __name__ == "__main__":
    test_query_points()
