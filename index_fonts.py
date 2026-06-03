import os
import sys
import argparse
from dotenv import load_dotenv
from font_es_service import FontMetadataService

def main():
    # Load environment variables
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="Font Metadata Indexer & Search Tool for Elasticsearch (HTTPS with User/Pass)"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Sub-command to execute")
    
    # Sub-command: index
    index_parser = subparsers.add_parser("index", help="Scan directory and index font metadata")
    index_parser.add_argument("dir", type=str, help="Directory path to scan for fonts")
    index_parser.add_argument(
        "--index-name", 
        type=str, 
        default="metadata", 
        help="Elasticsearch index name (default: metadata)"
    )
    
    # Sub-command: search
    search_parser = subparsers.add_parser("search", help="Search fonts in the Elasticsearch index")
    search_parser.add_argument("query", type=str, help="Text query to search for (e.g., 'Roboto' or 'bold')")
    search_parser.add_argument(
        "--index-name", 
        type=str, 
        default="metadata", 
        help="Elasticsearch index name (default: metadata)"
    )
    search_parser.add_argument(
        "--size", 
        type=int, 
        default=10, 
        help="Maximum number of results to display (default: 10)"
    )
    
    # Sub-command: ping
    subparsers.add_parser("ping", help="Ping the Elasticsearch instance to test authentication/connection")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return

    # Initialize the service
    try:
        service = FontMetadataService()
    except Exception as e:
        print(f"\n[Initialization Error]: {e}")
        print("Please check your .env credentials (ELASTICSEARCH_URL, ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD).")
        return

    if args.command == "ping":
        print(f"Pinging Elasticsearch at {service.es_url}...")
        try:
            if service.es.ping():
                print("Connection SUCCESS! Successfully authenticated and connected to Elasticsearch.")
            else:
                print("Connection FAILED! Could not reach Elasticsearch or authentication failed.")
        except Exception as e:
            print(f"Connection FAILED with error: {e}")
            
    elif args.command == "index":
        print(f"\nScanning directory: {args.dir}...")
        if not os.path.isdir(args.dir):
            print(f"Error: '{args.dir}' is not a valid directory path.")
            return
            
        try:
            res = service.index_directory(args.dir, index_name=args.index_name)
            print(f"\n[Indexing Summary] index: '{args.index_name}'")
            print("-" * 50)
            print(f"Total files processed: {res['total_processed']}")
            print(f"Successfully indexed:  {res['success_count']}")
            print(f"Failed files:          {res['fail_count']}")
            
            if res['fail_count'] > 0:
                print("\nErrors encountered:")
                for file, err in res['errors'].items():
                    print(f" - {file}: {err}")
                    
        except Exception as e:
            print(f"\n[Indexing Failed]: {e}")
            
    elif args.command == "search":
        print(f"\nSearching index '{args.index_name}' for query: '{args.query}'...\n")
        try:
            results = service.search_fonts(args.query, index_name=args.index_name, size=args.size)
            if not results:
                print("No matching fonts found.")
                return
                
            print("Top Matching Fonts:")
            print("=" * 110)
            print(f"{'No.':<4} | {'Score':<6} | {'Family':<20} | {'Subfamily':<12} | {'Format':<6} | {'Filename':<30} | {'Path'}")
            print("-" * 110)
            for i, hit in enumerate(results, start=1):
                src = hit["source"]
                family = src.get("family", "N/A")
                subfamily = src.get("subfamily", "N/A")
                fmt = src.get("format", "N/A")
                filename = src.get("file_name", "N/A")
                path = src.get("file_path", "N/A")
                print(f"{i:<4} | {hit['score']:<6.2f} | {family[:20]:<20} | {subfamily[:12]:<12} | {fmt:<6} | {filename[:30]:<30} | {path}")
            print("=" * 110)
        except Exception as e:
            print(f"\n[Search Failed]: {e}")

if __name__ == "__main__":
    main()
