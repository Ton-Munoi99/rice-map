import urllib.request, json, urllib.parse

url = "https://dataapi.moc.go.th/products?keyword=" + urllib.parse.quote("ปุ๋ย")
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read())
    
for d in data:
    if "46-0-0" in d.get("product_name", ""):
        print(d["product_id"], d["product_name"])
    if "15-15-15" in d.get("product_name", ""):
        print(d["product_id"], d["product_name"])
