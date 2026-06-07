import os
import httpx
import numpy as np
from dotenv import load_dotenv

load_dotenv(override=True)
url = os.getenv("EMBEDDING_API_URL", "http://171.232.252.198:8686/embed").strip()

# Descriptions from Qdrant scroll
descriptions = {
    "background-ghep-anh-21.jpg": "Một con hươu nhỏ đứng giữa lối mòn xanh mướt trong khu rừng rậm rạp với những tán cây xanh mướt và hoa tím điểm xuyết. Bức ảnh mang phong cách thiên nhiên tươi sáng, yên bình với tông màu xanh lá chủ đạo.",
    "91.jpg": "Bộ sưu tập các bục trưng bày sản phẩm 3D với nhiều hình dáng hình trụ và hình hộp chữ nhật khác nhau. Tất cả đều có màu trắng tối giản, phong cách hiện đại trên nền trắng sạch sẽ.",
    "1f26399e-08f2-429b-8ea7-5023b27ec899.jpg": "Hình ảnh là một bục trưng bày hình tròn màu nâu nhạt/be đặt trên nền tối giản cùng tông màu. Phong cách thiết kế 3D hiện đại, sạch sẽ với ánh sáng mềm mại, phù hợp để làm phông nền quảng cáo sản phẩm.",
    "green-pedestal-podium-product-display-stand-empty-space-stage-studio-background-3d-rendering.jpg": "Hình ảnh 3D tối giản với ba khối hình hộp chữ nhật màu xanh lá cây với các sắc độ đậm nhạt khác nhau, sắp xếp thành bục trưng bày. Toàn bộ khung cảnh nằm trên một nền màu xanh cốm nhạt, tạo phong cách hiện đại và sạch sẽ."
}

def get_emb(text):
    payload = {"inputs": [{"type": "text", "data": text}]}
    try:
        response = httpx.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return np.array(response.json()["embeddings"][0])
        else:
            print(f"Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")
    return None

# Generate description embeddings
desc_embs = {}
for name, desc in descriptions.items():
    desc_embs[name] = get_emb(desc)

queries = ["trắng", "màu trắng", "bục trắng", "bục trưng bày màu trắng", "bục tròn màu nâu", "podium"]

output = []
for q in queries:
    q_emb = get_emb(q)
    if q_emb is not None:
        output.append(f"Query: {q}")
        sims = []
        for name, d_emb in desc_embs.items():
            if d_emb is not None:
                sim = np.dot(q_emb, d_emb) / (np.linalg.norm(q_emb) * np.linalg.norm(d_emb))
                sims.append((name, sim))
        sims.sort(key=lambda x: x[1], reverse=True)
        for name, sim in sims:
            output.append(f"  - {name}: {sim:.4f}")
        output.append("-" * 40)

with open("scratch/description_search_results.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print("Successfully wrote description search results to scratch/description_search_results.txt")
