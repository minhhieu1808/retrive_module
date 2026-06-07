import os
import httpx
import numpy as np
from dotenv import load_dotenv
from image_retrieve_service import ImageRetrieveService

load_dotenv(override=True)
collection_name = os.getenv("QDRANT_COLLECTION", "vector_embeddings").strip()

service = ImageRetrieveService()

queries = ["trắng", "màu trắng", "bục trắng", "bục trưng bày màu trắng", "bục tròn màu nâu", "podium"]

CONTEXT_STOPWORDS = {
    "bục", "trưng", "bày", "màu", "hình", "ảnh", "3d", "sản", "phẩm", 
    "phông", "nền", "phong", "cách", "thiết", "kế", "cảnh", "khung", 
    "tông", "bộ", "sưu", "tập", "đặt", "trên", "những", "các", "có", "một"
}

def hybrid_search(query_text, top_k=4):
    # Standard vector search
    embeddings = service.generate_embeddings([{"type": "text", "data": query_text}])
    if not embeddings:
        return []
    
    vector = embeddings[0]
    results = service._search_by_vector(vector, collection_name, top_k=top_k)
    
    # Split query into words and filter out stopwords
    raw_words = [w.strip().lower() for w in query_text.replace(",", " ").replace(".", " ").split() if len(w.strip()) > 1]
    info_words = [w for w in raw_words if w not in CONTEXT_STOPWORDS]
    
    # If no informative words left, fallback to raw words
    target_words = info_words if info_words else raw_words
    
    boosted_results = []
    for res in results:
        desc = res.get("description", "").lower()
        match_count = 0
        if target_words:
            for qw in target_words:
                if qw in desc:
                    match_count += 1
            # Boost score based on keyword matches
            boost = 0.3 * (match_count / len(target_words))
        else:
            boost = 0.0
            
        original_score = res["score"]
        res["original_score"] = original_score
        res["score"] = original_score + boost
        res["percentage"] = round(((res["score"] + 1.0) / 2.0) * 100.0, 2)
        res["match_boost"] = boost
        res["target_words"] = target_words
        boosted_results.append(res)
        
    boosted_results.sort(key=lambda x: x["score"], reverse=True)
    return boosted_results

output = []
for q in queries:
    output.append(f"Query: {q}")
    results = hybrid_search(q, top_k=4)
    for i, res in enumerate(results):
        output.append(f"  {i+1}. File: {res.get('file_name')}")
        output.append(f"     Score: {res.get('score'):.4f} (Original: {res.get('original_score'):.4f}, Boost: {res.get('match_boost'):.4f})")
        output.append(f"     Target Words: {res.get('target_words')}")
        output.append(f"     Description: {res.get('description')}")
    output.append("=" * 60)

with open("scratch/hybrid_search_results_smart.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print("Successfully wrote hybrid search results to scratch/hybrid_search_results_smart.txt")
