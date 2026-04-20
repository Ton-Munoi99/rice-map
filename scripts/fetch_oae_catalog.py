import urllib.request
import json
import urllib.parse
import sys

sys.stdout.reconfigure(encoding='utf-8')

query = urllib.parse.quote('ครัวเรือน')
url = f'https://catalog.oae.go.th/api/3/action/package_search?q={query}'
try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    res = urllib.request.urlopen(req, timeout=10).read()
    data = json.loads(res.decode('utf-8'))
    
    print(f"Found {data['result']['count']} datasets.")
    for pack in data['result']['results'][:5]:
        print('--------------------')
        print(f"Title: {pack['title']}")
        for res in pack['resources']:
            print(f" - Resource: {res.get('name', 'N/A')} ({res.get('format', 'N/A')}): {res.get('url', 'N/A')}")
except Exception as e:
    print('Error:', e)
