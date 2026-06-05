import os
import sys
from dotenv import load_dotenv
from image_retrieve_service import ImageRetrieveService

def test_search():
    load_dotenv(override=True)
    
    collection_name = os.getenv("QDRANT_COLLECTION", "vector_embeddings").strip()
    print(f"Testing search on collection: {collection_name}")
    
    service = ImageRetrieveService()
    
    # Check collections
    try:
        collections = service.qdrant_client.get_collections()
        print("Available collections:")
        for c in collections.collections:
            print(f" - {c.name}")
    except Exception as e:
        print(f"Error listing collections: {e}")
        return
        
    # Scroll points
    try:
        points, _ = service.qdrant_client.scroll(
            collection_name=collection_name,
            limit=5,
            with_payload=True,
            with_vectors=False
        )
        print(f"\nPoints currently in collection:")
        for p in points:
            # Avoid charmap print error by encoding explicitly to utf-8 if needed, or printing repr
            print(f" - ID: {p.id}")
            print(f"   File: {p.payload.get('file_name')}")
            # print description safely
            desc = p.payload.get('description', '')
            print(f"   Description: {repr(desc)}")
            print(f"   Input Type: {p.payload.get('input_type')}")
    except Exception as e:
        print(f"Error scrolling points: {e}")
        
    # Test search
    query = "studio"
    print(f"\nTesting search with query: '{query}'")
    try:
        results = service.search_images(query, collection_name, top_k=3)
        print(f"Search results for '{query}':")
        for i, res in enumerate(results):
            print(f" {i+1}. File: {res.get('file_name')}")
            print(f"    Score: {res.get('score')} ({res.get('percentage')}%)")
            print(f"    Description: {repr(res.get('description'))}")
    except Exception as e:
        print(f"Error searching: {e}")

if __name__ == "__main__":
    test_search()
