import urllib.request
import re

url = "https://unsplash.com/s/photos/product-background"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        # Find all unsplash photo URLs in src/srcset attributes
        matches = re.findall(r'https://images\.unsplash\.com/photo-[a-zA-Z0-9\-]+', html)
        unique_matches = list(set(matches))
        print(f"Found {len(unique_matches)} unique images:")
        for m in unique_matches[:15]:
            print(m)
except Exception as e:
    print(f"Error: {e}")
