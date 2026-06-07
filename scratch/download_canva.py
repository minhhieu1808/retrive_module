import urllib.request
import os

# Ensure target folder 'image' exists
os.makedirs("image", exist_ok=True)

# 10 Unsplash IDs representing elegant Canva slide backgrounds (with negative space for text)
photo_ids = [
    "photo-1507525428034-b723cf961d3e", # Clean beach sunset (negative space)
    "photo-1501504905252-473c47e087f8", # Flat lay of desk with notebook, coffee (clean space)
    "photo-1616486338812-3dadae4b4ace", # Clean wooden table top against soft background
    "photo-1600585154340-be6161a56a0c", # Modern minimal house interior with empty wall
    "photo-1518531933037-91b2f5f229cc", # Subtle dark paper texture
    "photo-1507842217343-583bb7270b66", # Clean workspace environment (warm tones)
    "photo-1595152772835-219674b2a8a6", # Soft orange/yellow pastel background
    "photo-1512290923902-8a9f81dc236c", # Abstract paper shadow overlay (minimal)
    "photo-1554034483-04fda0d3507b", # Elegant gray wave pattern
    "photo-1497215728101-856f4ea42174"  # Clean office empty space (minimalist)
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

success_count = 0
for i, photo_id in enumerate(photo_ids, 1):
    image_url = f"https://images.unsplash.com/{photo_id}?w=1200&h=800&fit=crop&q=80"
    file_name = f"canva_{i}.jpg"
    file_path = os.path.join("image", file_name)
    
    print(f"Downloading Canva slide background {i}/10: {photo_id}...")
    req = urllib.request.Request(image_url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            with open(file_path, "wb") as f:
                f.write(response.read())
            print(f"Successfully saved to {file_path}")
            success_count += 1
    except Exception as e:
        print(f"Failed to download {photo_id}: {e}")

print(f"\nCompleted: {success_count}/10 Canva backgrounds successfully saved to 'image/'.")
