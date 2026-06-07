import urllib.request
import os

url = "https://loremflickr.com/1200/800/product,background?random=1"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req) as response:
        content_type = response.info().get_content_type()
        final_url = response.geturl()
        print(f"Content Type: {content_type}")
        print(f"Final URL: {final_url}")
        
        # Save to test.jpg
        with open("scratch/test_lorem.jpg", "wb") as f:
            f.write(response.read())
        print("Success! Downloaded to scratch/test_lorem.jpg")
except Exception as e:
    print(f"Error: {e}")
