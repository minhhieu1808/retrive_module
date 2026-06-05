import os
import sys
from dotenv import load_dotenv
from image_retrieve_service import ImageRetrieveService

def run_test():
    # Load environment variables
    load_dotenv(override=True)
    
    collection_name = os.getenv("QDRANT_COLLECTION", "vector_embeddings").strip()
    image_dir = "image"
    
    print("=== Start Image Indexing Process ===")
    print(f"Target Qdrant collection: '{collection_name}'")
    print(f"Target image directory: '{image_dir}'")
    
    # Check if directory exists
    if not os.path.exists(image_dir):
        print(f"Error: Directory '{image_dir}' does not exist.")
        return
        
    try:
        # Initialize Image Retrieval Service
        service = ImageRetrieveService()
        
        # Scan and index directory
        print(f"\nProcessing images and indexing to Qdrant...")
        res = service.index_directory(image_dir, collection_name)
        
        print("\n=== Indexing Summary ===")
        print(f"Total processed:  {res['total_processed']}")
        print(f"Success count:    {res['success_count']}")
        print(f"Fail count:       {res['fail_count']}")
        
        if res['fail_count'] > 0:
            print("\nErrors encountered:")
            for img_name, err in res['errors'].items():
                print(f"  - {img_name}: {err}")
                
        # Fetch current count from Qdrant
        collection_info = service.qdrant_client.get_collection(collection_name)
        print(f"\nFinal Qdrant Status: Collection '{collection_name}' has {collection_info.points_count} document(s).")
        
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
