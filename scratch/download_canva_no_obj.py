import urllib.request
import os

# Ensure target folder 'image' exists
os.makedirs("image", exist_ok=True)

# 10 Unsplash IDs representing aesthetic Canva slide backgrounds without physical objects
photo_ids = [
    "photo-1557683311-eac922347aa1", # Smooth blue gradient
    "photo-1579546929518-9e396f3cc809", # Rainbow abstract gradient
    "photo-1620641788421-7a1c342ea42e", # Pastel abstract wave
    "photo-1620121692029-d088224ddc74", # 3D render abstract backdrop
    "photo-1513542789411-b6a5d4f31634", # Soft blue/grey minimalist paint
    "photo-1560780552-ba54683cb263", # Light pastel green monotone texture
    "photo-1518531933037-91b2f5f229cc", # Subtle black/dark grey concrete texture
    "photo-1554034483-04fda0d3507b", # Elegant gray wave pattern
    "photo-1508898578281-774ac4893c0c", # Subtle brown/tan studio paper texture
    "photo-1579783902614-a3fb3927b6a5"  # Beige textured canvas backdrop
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

success_count = 0
for i, photo_id in enumerate(photo_ids, 1):
    image_url = f"https://images.unsplash.com/{photo_id}?w=1200&h=800&fit=crop&q=80"
    file_name = f"canva_no_obj_{i}.jpg"
    file_path = os.path.join("image", file_name)
    
    print(f"Downloading pure background {i}/10: {photo_id}...")
    req = urllib.request.Request(image_url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            with open(file_path, "wb") as f:
                f.write(response.read())
            print(f"Successfully saved to {file_path}")
            success_count += 1
    except Exception as e:
        print(f"Failed to download {photo_id}: {e}")

print(f"\nCompleted: {success_count}/10 Canva backgrounds without objects saved to 'image/'.")
