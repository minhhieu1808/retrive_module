import urllib.request
import urllib.parse
import re
import json

def get_ddg_images(query):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Step 1: Get vqd token
    enc_query = urllib.parse.quote(query)
    url = f"https://duckduckgo.com/?q={enc_query}&iax=images&ia=images"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            vqd_match = re.search(r'vqd=([0-9\-]+)', html)
            if not vqd_match:
                vqd_match = re.search(r'vqd=["\']([0-9\-]+)["\']', html)
            if not vqd_match:
                print("Could not find vqd token")
                return []
            vqd = vqd_match.group(1)
            print(f"Found vqd token: {vqd}")
            
        # Step 2: Fetch images JSON
        json_url = f"https://duckduckgo.com/i.js?l=us-en&o=json&q={enc_query}&vqd={vqd}&f=,,,"
        req = urllib.request.Request(json_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            results = data.get('results', [])
            return [r.get('image') for r in results if r.get('image')]
    except Exception as e:
        print(f"Error fetching DDG images: {e}")
        return []

urls = get_ddg_images("product background banner")
print(f"Found {len(urls)} URLs:")
for u in urls[:5]:
    print(u)
