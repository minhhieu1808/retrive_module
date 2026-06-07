import urllib.request
import os

# Create image directory if it doesn't exist
os.makedirs("image", exist_ok=True)

# List of high-quality Unsplash product banner/background photo IDs
photo_ids = [
    "photo-1579546929518-9e396f3cc809", # Rainbow abstract gradient
    "photo-1618005182384-a83a8bd57fbe", # 3D abstract shapes
    "photo-1557683316-973673baf926", # Red-blue abstract gradient
    "photo-1554034483-04fda0d3507b", # Fluid abstract gradient
    "photo-1550684848-fac1c5b4e853", # Black minimalist backdrop
    "photo-1604871000636-074fa5117945", # Minimal abstract canvas painting
    "photo-1578301978693-85fa9c0320b9", # Studio lighting backdrop
    "photo-1620641788421-7a1c342ea42e", # Pastel abstract wave
    "photo-1617396900799-f4ec2b43c7ae", # Vibrant fluid pattern
    "photo-1620121692029-d088224ddc74"  # 3D render abstract backdrop
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

success_count = 0
for i, photo_id in enumerate(photo_ids, 1):
    # Unsplash source URL (using w=1200, h=800, fit=crop for optimal banner size and fast download)
    image_url = f"https://images.unsplash.com/{photo_id}?w=1200&h=800&fit=crop&q=80"
    file_path = os.path.join("image", f"banner_{i}.jpg")
    
    print(f"Downloading image {i}/10: {photo_id}...")
    req = urllib.request.Request(image_url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            with open(file_path, "wb") as f:
                f.write(response.read())
            print(f"Successfully saved to {file_path}")
            success_count += 1
    except Exception as e:
        print(f"Failed to download {photo_id}: {e}")

print(f"\nDownload completed: {success_count}/10 images successfully saved to 'image/' folder.")
