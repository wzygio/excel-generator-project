"""
探针: 探索 entry 端点获取报表 UUID
"""
from __future__ import annotations
import os, re, json

os.environ["NO_PROXY"] = "10.73.17.76"
import requests

HOST = "http://10.73.17.76:8080"
session = requests.Session()

# Login
resp = session.post(
    f"{HOST}/webroot/decision/login",
    json={"username": "V0141351", "password": "PnM59pIOFbEAzj5pq7YYPA==", "validity": -1, "encrypted": True},
    timeout=15,
)
token = resp.json().get("data", {}).get("accessToken")
session.headers.update({"Authorization": f"Bearer {token}", "X-Requested-With": "XMLHttpRequest"})
session.cookies.set("fine_auth_token", token, domain="10.73.17.76", path="/")
print(f"Login OK, token: {token[:20]}...")

# Step 1: Get known report UUID details
print("\n=== Known report UUID info ===")
resp = session.get(f"{HOST}/webroot/decision/v10/entry", params={"entryId": "22ce8bfb-620c-485f-a521-2fae23f53b63"}, timeout=15)
data = resp.json().get("data", {})
print(f"Known report: {json.dumps(data, ensure_ascii=False, indent=2)}")

# Step 2: Check V3 yield directory UUID details
print("\n=== V3 yield directory UUID info ===")
resp = session.get(f"{HOST}/webroot/decision/v10/entry", params={"entryId": "08384cea-3738-4f5f-acb3-ec43878d9c01"}, timeout=15)
data = resp.json().get("data", {})
print(f"V3 dir: {json.dumps(data, ensure_ascii=False, indent=2)}")

# Step 3: Try to list children of V3 yield directory
print("\n=== Try listing children via various endpoints ===")
v3_dir_uuid = "08384cea-3738-4f5f-acb3-ec43878d9c01"

# Method A: entry with parentId
endpoints = [
    f"{HOST}/webroot/decision/v10/entry?parentId={v3_dir_uuid}",
    f"{HOST}/webroot/decision/v10/entry/tree?parentId={v3_dir_uuid}",
    f"{HOST}/webroot/decision/v10/entry/list?parentId={v3_dir_uuid}",
    f"{HOST}/webroot/decision/v10/entry/tree?entryId={v3_dir_uuid}",
]
for url in endpoints:
    try:
        resp = session.get(url, timeout=15)
        preview = resp.text[:300]
        print(f"  GET {url} -> {resp.status_code}, len={len(resp.text)}")
        print(f"    Preview: {preview}")
    except Exception as e:
        print(f"    FAIL: {e}")

# Step 4: Get ALL entries from full directory and check their entryType
print("\n=== Scan all directory items for child reports ===")
resp = session.get(f"{HOST}/webroot/decision/v10/directory", params={"keyword": "", "parentId": ""}, timeout=15)
items = resp.json().get("data", [])

# For each directory, try to find its report children
# Strategy: keyword search with the directory name
print("\n--- Searching for reports using keyword ---")
target_kws = ["V3良率", "月周天", "批次汇总", "V3良率及不良率"]
for kw in target_kws:
    try:
        resp = session.get(f"{HOST}/webroot/decision/v10/entry", params={"keyword": kw}, timeout=15)
        print(f"  keyword={kw}: status={resp.status_code}, len={len(resp.text)}")
        if resp.status_code == 200 and len(resp.text) > 20:
            try:
                data = resp.json()
                print(f"    Response: {json.dumps(data, ensure_ascii=False)[:500]}")
            except:
                print(f"    Raw: {resp.text[:300]}")
    except Exception as e:
        print(f"    FAIL: {e}")

# Step 5: Try POST directory/search with keyword
print("\n--- POST search for V3 target reports ---")
try:
    resp = session.post(
        f"{HOST}/webroot/decision/v10/directory/search",
        params={"keyword": "V3良率"},
        timeout=15,
    )
    print(f"  POST /directory/search?keyword=V3良率 -> {resp.status_code}, len={len(resp.text)}")
    if len(resp.text) > 50:
        print(f"    Response: {resp.text[:300]}")
except Exception as e:
    print(f"    FAIL: {e}")

# Step 6: Try to get entry children of the V3 directory
print("\n--- Trying POST entry children endpoints ---")
try:
    resp = session.post(
        f"{HOST}/webroot/decision/v10/entry",
        params={"entryId": v3_dir_uuid},
        timeout=15,
    )
    print(f"  POST /entry?entryId={v3_dir_uuid} -> {resp.status_code}, len={len(resp.text)}")
    if len(resp.text) > 50:
        print(f"    Response: {resp.text[:300]}")
except Exception as e:
    print(f"    FAIL: {e}")

# Step 7: Check the deviceType and entryType patterns
print("\n=== Entry type analysis ===")
# From the known report: entryType=102, deviceType=7
# From directories: entryType=3, deviceType=7
# entryType 102 = REPORT
# entryType 3 = DIRECTORY

# Try to find entries with different entryTypes
for item in items[:5]:
    item_id = item.get("id", "")
    text = item.get("text", "")
    resp = session.get(f"{HOST}/webroot/decision/v10/entry", params={"entryId": item_id}, timeout=15)
    data = resp.json().get("data", {})
    etype = data.get("entryType", "?")
    path = data.get("path", "")
    print(f"  ID={item_id}, text={text}, entryType={etype}, path={path}")

print("\nDone")
