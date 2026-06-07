import urllib.request
import json

url = "https://unsplash.com/napi/search/photos?query=banner-background&per_page=30&page=1"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        results = data.get('results', [])
        print(f"Successfully fetched page 1! Found {len(results)} images.")
        if results:
            print("First image URL:", results[0]['urls']['regular'])
except Exception as e:
    print(f"Error: {e}")
