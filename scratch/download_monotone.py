import urllib.request
import os

# Ensure target folder 'image' exists
os.makedirs("image", exist_ok=True)

# 10 Unsplash IDs representing simple monotone background banner slides
photo_ids = [
    "photo-1557672172-298e090bd0f1", # Monotone gray/white abstract paint texture
    "photo-1579783902614-a3fb3927b6a5", # Beige monotone textured canvas
    "photo-1513542789411-b6a5d4f31634", # Soft blue/grey minimalist background
    "photo-1560780552-ba54683cb263", # Light pastel green monotone texture
    "photo-1554034483-04fda0d3507b", # Subtle abstract wave monotone backdrop
    "photo-1528459801416-a9e53bbf4e17", # Clean concrete grey studio background
    "photo-1508898578281-774ac4893c0c", # Subtle brown/tan studio paper texture
    "photo-1607604276583-eef5d076aa5f", # Deep navy blue solid wall texture
    "photo-1563089145-599997674d42", # Purple/pink soft neon gradient
    "photo-1518531933037-91b2f5f229cc"  # Subtle black/dark grey concrete backdrop
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

success_count = 0
for i, photo_id in enumerate(photo_ids, 1):
    image_url = f"https://images.unsplash.com/{photo_id}?w=1200&h=800&fit=crop&q=80"
    file_name = f"monotone_{i}.jpg"
    file_path = os.path.join("image", file_name)
    
    print(f"Downloading monotone background {i}/10: {photo_id}...")
    req = urllib.request.Request(image_url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            with open(file_path, "wb") as f:
                f.write(response.read())
            print(f"Successfully saved to {file_path}")
            success_count += 1
    except Exception as e:
        print(f"Failed to download {photo_id}: {e}")

print(f"\nCompleted: {success_count}/10 monotone backgrounds successfully saved to 'image/'.")
