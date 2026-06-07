import urllib.request
import os

# Ensure target folder 'image' exists
os.makedirs("image", exist_ok=True)

# 10 Unsplash IDs representing Viettel (corporate, telecom, network) and traditional Vietnamese people/landscapes
photo_ids = [
    "photo-1528127269322-539801943592", # Vietnamese woman in red Ao Dai and Non La (conical hat) in Hue
    "photo-1473448912268-2022ce9509d8", # Scenic night skyline of Ho Chi Minh City, Vietnam
    "photo-1526481280693-3bfa7568e0f3", # Hoi An traditional lantern street
    "photo-1555939594-58d7cb561ad1", # Traditional Vietnamese Pho (culinary culture)
    "photo-1508009603885-50cf7c579365", # Conical hat Non La on a wooden boat
    "photo-1569154941061-e231b4725ef1", # Classic Hanoi train streetscape
    "photo-1451187580459-43490279c0fa", # Digital earth network (representing Viettel Global)
    "photo-1562408590-e32931084e23", # Telecommunications antenna tower (representing network coverage)
    "photo-1486406146926-c627a92ad1ab", # Modern glass corporate skyscraper (representing Viettel HQ)
    "photo-1557683316-973673baf926"  # Solid red/orange corporate brand color gradient
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

success_count = 0
for i, photo_id in enumerate(photo_ids, 1):
    image_url = f"https://images.unsplash.com/{photo_id}?w=1200&h=800&fit=crop&q=80"
    file_name = f"vietnam_viettel_{i}.jpg"
    file_path = os.path.join("image", file_name)
    
    print(f"Downloading Vietnam/Viettel image {i}/10: {photo_id}...")
    req = urllib.request.Request(image_url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            with open(file_path, "wb") as f:
                f.write(response.read())
            print(f"Successfully saved to {file_path}")
            success_count += 1
    except Exception as e:
        print(f"Failed to download {photo_id}: {e}")

print(f"\nCompleted: {success_count}/10 Vietnam/Viettel images successfully saved to 'image/'.")
