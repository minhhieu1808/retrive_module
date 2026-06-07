import os
import base64
from dotenv import load_dotenv
from image_retrieve_service import ImageRetrieveService

load_dotenv(override=True)
collection_name = os.getenv("QDRANT_COLLECTION", "vector_embeddings").strip()

service = ImageRetrieveService()

img_files = [
    "91.jpg",
    "1f26399e-08f2-429b-8ea7-5023b27ec899.jpg",
    "green-pedestal-podium-product-display-stand-empty-space-stage-studio-background-3d-rendering.jpg",
    "background-ghep-anh-21.jpg"
]

output = []
for query_name in img_files:
    query_path = os.path.join("image", query_name)
    with open(query_path, "rb") as f:
        img_bytes = f.read()
    encoded = base64.b64encode(img_bytes).decode('utf-8')
    image_base64 = f"data:image/jpeg;base64,{encoded}"
    
    output.append(f"Query Image: {query_name}")
    results = service.search_images_by_image(image_base64, collection_name, top_k=4)
    for i, res in enumerate(results):
        output.append(f"  {i+1}. File: {res.get('file_name')}")
        output.append(f"     Score: {res.get('score')} ({res.get('percentage')}%)")
    output.append("=" * 60)

with open("scratch/image_to_image_search_results.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print("Successfully wrote image-to-image search results to scratch/image_to_image_search_results.txt")
