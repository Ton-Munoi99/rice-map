import urllib.request
import json
import urllib.parse
import time

def find_ids():
    terms = ['46-0-0', '16-20-0', '15-15-15', 'ปุ๋ยยูเรีย']
    for t in terms:
        print(f"Searching for: {t}")
        url = f'https://dataapi.moc.go.th/products?keyword={urllib.parse.quote(t)}'
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                for d in data:
                    print(f"  FOUND: {d.get('product_id')} - {d.get('product_name')}")
        except Exception as e:
            print(f"  Error: {e}")
        time.sleep(1)

if __name__ == "__main__":
    find_ids()
