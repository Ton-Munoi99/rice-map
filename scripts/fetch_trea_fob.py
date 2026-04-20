import urllib.request
import ssl
from bs4 import BeautifulSoup
import json
import os
import re

def fetch_trea_fob():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    url = 'https://www.thairiceexporters.or.th/price.htm'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    html = urllib.request.urlopen(req, context=ctx).read()
    try:
        html_str = html.decode('cp874', errors='ignore')
    except:
        html_str = html.decode('utf-8', errors='ignore')
    
    soup = BeautifulSoup(html_str, 'html.parser')
    
    dates = []
    prices = {}
    
    rows = soup.find_all('tr')
    for row in rows:
        tds = row.find_all('td')
        if not tds:
            continue
        texts = [t.get_text(strip=True) for t in tds if t.get_text(strip=True)]
        if not texts:
            continue
            
        row_str = " | ".join(texts)
        if 'Item' in texts[0] and not dates:
            # First column is Item, the rest are dates
            # DIT tables often have missing closing tags, use regex to extract valid dates
            import re
            for t_text in texts:
                # Find all dates in format "8 Apr  2026" or similar
                found = re.findall(r'\d{1,2}\s+[a-zA-Z]+\s+\d{4}', t_text)
                for f in found:
                    if f not in dates:
                        dates.append(f)
        
        elif 'Thai Hom Mali Rice - Premium' in texts[0] and '(68/69)' in texts[0] or '(2025/26)' in texts[0]:
            # Jasmine Rice
            if len(texts) > 1 and texts[-1].isdigit():
                prices['jasmine_fob'] = int(texts[-1])
        
        elif 'White Rice 5%' in texts[0]:
            # White Rice 5%
            if len(texts) > 1 and texts[-1].isdigit():
                prices['white_fob'] = int(texts[-1])
                
    if not dates:
        print("Could not find dates header")
        return

    latest_date = dates[-1]
    
    output = {
        "date": latest_date,
        "unit": "USD/MT",
        "prices": prices,
        "source": "Thai Rice Exporters Association (TREA)"
    }
    
    print("Extracted FOB Prices:")
    print(json.dumps(output, indent=2))
    
    # Save to data/trea-fob.json
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'trea-fob.json')
    
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        
    print(f"Saved to {out_path}")

if __name__ == '__main__':
    fetch_trea_fob()
