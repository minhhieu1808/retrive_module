import urllib.request
import os

# Ensure target folder 'image' exists
os.makedirs("image", exist_ok=True)

# 10 Unsplash IDs representing empty podium/pedestal display stands (no products)
photo_ids = [
    "photo-1618005182384-a83a8bd57fbe", # Minimalist 3D abstract shapes podium
    "photo-1512290923902-8a9f81dc236c", # Empty concrete podium stand with shadow
    "photo-1615485290382-441e4d049cb5", # Empty circular concrete podium
    "photo-1614850523459-c2f4c699c52e", # Geometric white empty platform
    "photo-1549490349-8643362247b5", # Empty round wooden pedestal with plant shadow
    "photo-1613545325278-f24b0cae1224", # Minimalist beige ceramic empty display stand
    "photo-1596461404969-9ae70f2830c1", # Empty cylinder backdrop platform
    "photo-1579546929518-9e396f3cc809", # Smooth gradient backdrop (no product)
    "photo-1554034483-04fda0d3507b", # Smooth fluid backdrop (no product)
    "photo-1620121692029-d088224ddc74"  # 3D render abstract empty backdrop
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

success_count = 0
for i, photo_id in enumerate(photo_ids, 1):
    image_url = f"https://images.unsplash.com/{photo_id}?w=1200&h=800&fit=crop&q=80"
    file_name = f"podium_empty_{i}.jpg"
    file_path = os.path.join("image", file_name)
    
    print(f"Downloading clean podium image {i}/10: {photo_id}...")
    req = urllib.request.Request(image_url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            with open(file_path, "wb") as f:
                f.write(response.read())
            print(f"Successfully saved to {file_path}")
            success_count += 1
    except Exception as e:
        print(f"Failed to download {photo_id}: {e}")

print(f"\nCompleted: {success_count}/10 empty podium background images successfully saved to 'image/'.")
