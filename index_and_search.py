import os
import argparse
import uuid
from pathlib import Path
from dotenv import load_dotenv
from es_image_service import ElasticsearchImageService

# Supported image file formats
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}

def main():
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="Elasticsearch Multimodal Image Indexing & Semantic Search Tool"
    )
    parser.add_argument(
        "--provider", 
        type=str, 
        default="gemini", 
        choices=["gemini", "clip"], 
        help="Embedding provider: 'gemini' (multimodal cloud API) or 'clip' (local model). Default: gemini"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Sub-command to run")
    
    # Sub-command: index
    index_parser = subparsers.add_parser("index", help="Index images from a local directory")
    index_parser.add_argument("dir", type=str, help="Path to the directory containing images")
    index_parser.add_argument(
        "--index-name", 
        type=str, 
        default="image_embedding", 
        help="Elasticsearch index name (default: image_embedding)"
    )
    
    # Sub-command: search
    search_parser = subparsers.add_parser("search", help="Search images using a text description query")
    search_parser.add_argument("query", type=str, help="Text query describing the image (e.g. 'a blue shoes')")
    search_parser.add_argument(
        "--index-name", 
        type=str, 
        default="image_embedding", 
        help="Elasticsearch index name (default: image_embedding)"
    )
    search_parser.add_argument(
        "--top", 
        type=int, 
        default=5, 
        help="Number of search results to return (default: 5)"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return

    # Initialize the service
    try:
        service = ElasticsearchImageService(provider=args.provider)
    except Exception as e:
        print(f"\n[Error Initializing Service]: {e}")
        print("Please check your .env settings (e.g. GEMINI_API_KEY, ELASTICSEARCH_URL).")
        return

    if args.command == "index":
        run_indexing(service, args.dir, args.index_name)
    elif args.command == "search":
        run_searching(service, args.query, args.index_name, args.top)

def run_indexing(service: ElasticsearchImageService, directory_path: str, index_name: str):
    dir_path = Path(directory_path)
    if not dir_path.is_dir():
        print(f"Error: Directory '{directory_path}' does not exist.")
        return

    # Create the index if it doesn't already exist
    service.create_index(index_name)
    
    # Scan the folder for images
    image_paths = []
    for ext in IMAGE_EXTENSIONS:
        image_paths.extend(dir_path.glob(f"*{ext}"))
        image_paths.extend(dir_path.glob(f"*{ext.upper()}"))
        
    if not image_paths:
        print(f"No images found in '{directory_path}' with extensions: {IMAGE_EXTENSIONS}")
        return
        
    print(f"\nFound {len(image_paths)} images to index in '{directory_path}'. Starting indexing...")
    
    success_count = 0
    for img_path in image_paths:
        doc_id = f"{uuid.uuid4().hex[:8]}_{img_path.name}"
        try:
            print(f" -> Indexing [{img_path.name}] ... ", end="", flush=True)
            abs_path = str(img_path.resolve())
            
            service.index_image(
                doc_id=doc_id,
                image_path_or_bytes=abs_path,
                index_name=index_name,
                metadata={
                    "filename": img_path.name,
                    "indexed_from": str(dir_path.resolve())
                }
            )
            print("SUCCESS")
            success_count += 1
        except Exception as e:
            print(f"FAILED ({e})")
            
    print(f"\n[Finished]: Successfully indexed {success_count}/{len(image_paths)} images into index '{index_name}'.")

def run_searching(service: ElasticsearchImageService, query_text: str, index_name: str, top_k: int):
    print(f"\nSearching index '{index_name}' for description: '{query_text}'...\n")
    try:
        results = service.search_by_text(query_text, index_name=index_name, top_k=top_k)
        if not results:
            print("No matching images found.")
            return
            
        print("Top Matching Results:")
        print("-" * 90)
        print(f"{'No.':<4} | {'Score':<8} | {'Filename':<30} | {'Absolute Path'}")
        print("-" * 90)
        for i, hit in enumerate(results, start=1):
            filename = hit["metadata"].get("filename", "N/A")
            print(f"{i:<4} | {hit['score']:<8.4f} | {filename:<30} | {hit['image_path']}")
        print("-" * 90)
    except Exception as e:
        print(f"[Error executing search]: {e}")

if __name__ == "__main__":
    main()
