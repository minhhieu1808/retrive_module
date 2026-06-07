import os
import json
from qdrant_client import QdrantClient
from dotenv import load_dotenv
from image_retrieve_service import ImageRetrieveService

load_dotenv(override=True)
collection_name = os.getenv("QDRANT_COLLECTION", "vector_embeddings").strip()

service = ImageRetrieveService()

queries = ["trắng", "màu trắng", "bục trắng", "bục trưng bày màu trắng", "bục tròn màu nâu", "podium"]

output = []
for q in queries:
    output.append(f"Query: {q}")
    results = service.search_images(q, collection_name, top_k=4)
    for i, res in enumerate(results):
        output.append(f"  {i+1}. File: {res.get('file_name')}")
        output.append(f"     Score: {res.get('score')} ({res.get('percentage')}%)")
        output.append(f"     Description: {res.get('description')}")
    output.append("=" * 60)

with open("scratch/search_utf8_results.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print("Successfully wrote search results in UTF-8 to scratch/search_utf8_results.txt")
