import urllib.request
import urllib.parse
import http.cookiejar

cookie_jar = http.cookiejar.CookieJar()
handler = urllib.request.HTTPCookieProcessor(cookie_jar)
opener = urllib.request.build_opener(handler)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1'
}

url = "https://unsplash.com/s/photos/banner-background"
req = urllib.request.Request(url, headers=headers)

try:
    with opener.open(req) as response:
        print("Status code:", response.status)
        print("Cookies:")
        for cookie in cookie_jar:
            print(f"  {cookie.name}: {cookie.value}")
        html = response.read().decode('utf-8')
        print("HTML length:", len(html))
        # Look for photo IDs
        import re
        matches = re.findall(r'images\.unsplash\.com/(photo-[a-zA-Z0-9\-]+)', html)
        print(f"Found {len(set(matches))} unique photo IDs in HTML.")
except Exception as e:
    print("Error:", e)
