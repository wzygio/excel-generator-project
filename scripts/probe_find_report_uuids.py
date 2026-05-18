"""
probe_find_report_uuids.py: 探针脚本 v4 — 发现目标报表的入口 UUID

关键发现: GET /webroot/decision/v10/directory?keyword=&parentId= 返回完整目录树
需要从中找到叶子节点和实际的 CPT 报表 UUID
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import requests

os.environ["NO_PROXY"] = "10.73.17.76"

HOST = "http://10.73.17.76:8080"
USERNAME = "V0141351"
PASSWORD = "PnM59pIOFbEAzj5pq7YYPA=="

session = requests.Session()


def login() -> str:
    resp = session.post(
        f"{HOST}/webroot/decision/login",
        json={"username": USERNAME, "password": PASSWORD, "validity": -1, "encrypted": True},
        timeout=15,
    )
    data = resp.json()
    token = data.get("data", {}).get("accessToken")
    if not token:
        print(f"[FAIL] Login failed: {resp.text[:200]}")
        sys.exit(1)
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Requested-With": "XMLHttpRequest",
    })
    session.cookies.set("fine_auth_token", token, domain="10.73.17.76", path="/")
    print(f"[OK] Login OK, Token: {token[:20]}...")
    return token


def get_full_directory() -> list[dict]:
    """获取完整目录树"""
    url = f"{HOST}/webroot/decision/v10/directory"
    resp = session.get(url, params={"keyword": "", "parentId": ""}, timeout=15)
    if resp.status_code == 200:
        data = resp.json()
        items = data.get("data", [])
        print(f"Full directory: {len(items)} entries, {len(resp.text)} bytes")
        return items
    print(f"Failed to get directory: {resp.status_code}")
    return []


def try_entry_access(uuid: str) -> dict | None:
    """尝试访问 entry/access/{uuid}"""
    url = f"{HOST}/webroot/decision/v10/entry/access/{uuid}"
    try:
        resp = session.get(url, timeout=15)
        title = ""
        title_match = re.search(r'<title>(.*?)</title>', resp.text)
        if title_match:
            title = title_match.group(1)

        has_table = bool(re.search(r'<td[^>]*>', resp.text))
        data_len = len(resp.text)

        # Check for real data (not error)
        is_error = "errorCode" in resp.text[:500] if resp.text else True
        is_valid = data_len > 1000 and not is_error and has_table

        result = {
            "uuid": uuid,
            "status": resp.status_code,
            "length": data_len,
            "title": title,
            "has_table": has_table,
            "is_valid": is_valid,
            "has_target": False,
        }

        # Check for target report names
        for target in ["V3良率及不良率By月周天汇总", "V3良率及不良率By批次汇总"]:
            if target in resp.text:
                result["has_target"] = True
                result["target_found"] = target

        return result
    except Exception as e:
        return {"uuid": uuid, "error": str(e)}


def main():
    print("=" * 60)
    print("FineReport UUID Probe v4")
    print("=" * 60)
    login()

    # Step 1: Get full directory tree
    print("\n--- Step 1: Get full directory tree ---")
    all_items = get_full_directory()
    if not all_items:
        print("No directory items found!")
        sys.exit(1)

    # Classify entries
    dir_nodes = []
    leaf_nodes = []
    for item in all_items:
        is_parent = item.get("isParent", False)
        entry_type = item.get("entryType", 0)
        item_id = item.get("id", "")
        text = item.get("text", "")

        entry_info = {
            "id": item_id,
            "text": text,
            "pid": item.get("pId", ""),
            "is_parent": is_parent,
            "entry_type": entry_type,
        }

        if is_parent:
            dir_nodes.append(entry_info)
        else:
            leaf_nodes.append(entry_info)

    print(f"\nDirectory nodes: {len(dir_nodes)}")
    print(f"Leaf nodes: {len(leaf_nodes)}")

    # Print leaf nodes (potential reports)
    if leaf_nodes:
        print("\n--- Leaf nodes (potential reports) ---")
        for node in leaf_nodes:
            print(f"  [LEAF] {node['text']} (id={node['id']})")
    else:
        print("\nNo leaf nodes found - ALL entries are directory nodes")
        # Print all entries for debugging
        print("\n--- All directory entries ---")
        for node in dir_nodes:
            print(f"  [DIR] {node['text']} (id={node['id']}, pid={node['pid']})")

    # Step 2: Build parent->children map
    children_map: dict[str, list[dict]] = {}
    for item in all_items:
        pid = item.get("pId") or ""
        children_map.setdefault(pid, []).append(item)

    # Step 3: Try to access the "决策平台" main page to find more clues
    print("\n--- Step 3: Access main decision page ---")
    try:
        resp = session.get(f"{HOST}/webroot/decision", timeout=15)
        print(f"Main page: {resp.status_code}, {len(resp.text)} bytes")

        # Find all entry/access references
        entry_refs = re.findall(r'entry/access/([a-f0-9\-]{36})', resp.text)
        if entry_refs:
            unique = list(set(entry_refs))
            print(f"Entry access refs found: {unique}")

        # Find all UUIDs
        all_uuids = re.findall(r'[a-f0-9\-]{36}', resp.text)
        unique_all = list(set(all_uuids))
        print(f"Total unique UUIDs: {len(unique_all)}")

        # Search for target report names
        for target in ["V3良率", "月周天", "批次汇总"]:
            if target in resp.text:
                idx = resp.text.index(target)
                print(f"Found '{target}' at pos {idx}")
                print(f"  Context: ...{resp.text[max(0,idx-80):idx+len(target)+80]}...")

        # Save main page for analysis
        main_page_path = Path("scripts/decision_main_page.html")
        main_page_path.write_text(resp.text, encoding="utf-8")
        print(f"Saved main page to {main_page_path}")

    except Exception as e:
        print(f"  [FAIL] {e}")

    # Step 4: Try to access the main page with ?entryType=1 parameters
    print("\n--- Step 4: Explore additional endpoints ---")
    extra_tries = [
        f"{HOST}/webroot/decision/url/map",
        f"{HOST}/webroot/decision/v10/directory/searchReport",
        f"{HOST}/webroot/decision/v10/entry",
        f"{HOST}/webroot/decision/v10/report",
    ]
    for url in extra_tries:
        try:
            resp = session.get(url, timeout=15)
            print(f"  GET {url} -> {resp.status_code}, len={len(resp.text)}")
            if resp.status_code == 200 and len(resp.text) > 50:
                print(f"  Preview: {resp.text[:200]}")
        except Exception as e:
            print(f"  [FAIL] {e}")

    print("\n" + "=" * 60)
    print("Probe complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
