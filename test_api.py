# -*- coding: utf-8 -*-
import urllib.request
import json

try:
    data = json.dumps({"keyword": "欧文"}).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:5000/api/search", data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        body = resp.read().decode("utf-8")
        print(f"Status code: {resp.status}")
        result = json.loads(body)
        print(f"Total items: {len(result)}")
        if len(result) > 0:
            print(f"First item: {json.dumps(result[0], ensure_ascii=False, indent=2)}")
            print(f"Last item: {json.dumps(result[-1], ensure_ascii=False, indent=2)}")
        else:
            print("No data returned!")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code} {e.reason}")
    print(f"Response body: {e.read().decode('utf-8', errors='replace')[:2000]}")
except Exception as e:
    print(f"Request error: {type(e).__name__}: {e}")
