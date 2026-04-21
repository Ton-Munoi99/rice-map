import urllib.request, json

url = 'https://dataapi.moc.go.th/products'
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read().decode('utf-8'))
    
print(type(data))
if isinstance(data, list):
    for d in data[:5]:
        print(d)
    
    ferts = [d for d in data if isinstance(d, dict) and 'ปุ๋ย' in d.get('product_name', '')]
    print(f"Found {len(ferts)} fertilizers")
    for f in ferts:
        print(f["product_id"], f["product_name"])
elif isinstance(data, dict):
    print("Keys:", data.keys())
    # maybe data['data']
