import os
import base64
import io
from PIL import Image
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

def preprocess_image(file_path):
    with Image.open(file_path) as img:
        img.thumbnail((512, 512))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        img_bytes = buffer.getvalue()
    encoded = base64.b64encode(img_bytes).decode('utf-8')
    return f"data:image/jpeg;base64,{encoded}"

output = []
for query_name in img_files:
    query_path = os.path.join("image", query_name)
    image_base64 = preprocess_image(query_path)
    
    output.append(f"Query Image (Resized): {query_name}")
    results = service.search_images_by_image(image_base64, collection_name, top_k=4)
    for i, res in enumerate(results):
        output.append(f"  {i+1}. File: {res.get('file_name')}")
        output.append(f"     Score: {res.get('score')} ({res.get('percentage')}%)")
    output.append("=" * 60)

with open("scratch/image_to_image_search_resized_results.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print("Successfully wrote resized search results to scratch/image_to_image_search_resized_results.txt")
