"""
debug_finereport.py: FineReport API 调试脚本
直接输出 page_content 返回的原始 HTML 结构，帮助诊断数据不对的问题。
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("yield_report").setLevel(logging.DEBUG)

# 强制 NO_PROXY
os.environ["NO_PROXY"] = "10.73.17.76"

from yield_report.yield_report.infrastructure.finereport_client import FinereportClient


def main():
    print("=" * 60)
    print("FineReport API 调试")
    print("=" * 60)

    # 方案A: 带产品型号筛选
    print("\n--- 方案A: 发送产品型号筛选 ---")
    try:
        client = FinereportClient()
        client._login()
        client._acquire_session()

        # 提交筛选参数（只发一个型号）
        params = {"cmcbEQPID": "C472"}
        client._submit_parameters(params)

        # 获取数据
        html = client._fetch_page_content()
        print(f"\nHTML 长度: {len(html)}")
        print(f"HTML 前 2000 字符:\n{html[:2000]}")
        print(f"\nHTML 后 1000 字符:\n...{html[-1000:]}")
    except Exception as e:
        print(f"方案A 失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)

    # 方案B: 无任何筛选参数
    print("\n--- 方案B: 不发送任何筛选参数 ---")
    try:
        client2 = FinereportClient()
        client2._login()
        client2._acquire_session()

        # 不提交任何筛选参数

        # 获取数据
        html2 = client2._fetch_page_content()
        print(f"\nHTML 长度: {len(html2)}")
        print(f"HTML 前 2000 字符:\n{html2[:2000]}")
        print(f"\nHTML 后 1000 字符:\n...{html2[-1000:]}")
    except Exception as e:
        print(f"方案B 失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)

    # 方案C: 查看入口页返回的完整 HTML（查找报告结构线索）
    print("\n--- 方案C: 入口页 HTML 分析 ---")
    try:
        import requests
        import re

        host = "http://10.73.17.76:8080"
        uuid = "22ce8bfb-620c-485f-a521-2fae23f53b63"

        session = requests.Session()
        # 先登录
        resp = session.post(
            f"{host}/webroot/decision/login",
            json={
                "username": "V0141351",
                "password": "PnM59pIOFbEAzj5pq7YYPA==",
                "validity": -1,
                "encrypted": True,
            },
            timeout=15,
        )
        token = resp.json()["data"]["accessToken"]
        session.headers.update({
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "X-Requested-With": "XMLHttpRequest",
        })
        session.cookies.set("fine_auth_token", token)

        # 访问入口页
        entry_resp = session.get(f"{host}/webroot/decision/v10/entry/access/{uuid}", timeout=15)
        print(f"入口页状态码: {entry_resp.status_code}")
        print(f"入口页长度: {len(entry_resp.text)}")

        # 提取 sessionID
        match = re.search(r"FR\.SessionMgr\.register\('([a-f0-9\-]{36})'", entry_resp.text)
        if match:
            sid = match.group(1)
            print(f"Session ID: {sid}")

            # 直接获取数据（不提交任何参数）
            data_resp = session.get(
                f"{host}/webroot/decision/view/report?op=page_content&pn=1&sessionID={sid}",
                headers={"sessionID": sid, "X-Requested-With": "XMLHttpRequest"},
                timeout=120,
            )
            print(f"数据页状态码: {data_resp.status_code}")
            print(f"数据页长度: {len(data_resp.text)}")
            print(f"数据页前 3000 字符:\n{data_resp.text[:3000]}")
        else:
            print("入口页中未找到 sessionID")

        # 搜索入口页中是否有 cpt/viewlet 线索
        cpt_matches = re.findall(r'viewlet[^"]*\.cpt', entry_resp.text)
        if cpt_matches:
            print(f"\n发现 CPT 引用: {cpt_matches[:5]}")
        else:
            print("\n入口页中未发现 CPT 引用")

        # 搜索入口页中的 widget 配置
        widget_matches = re.findall(r'widgetName[^,]+', entry_resp.text)
        if widget_matches:
            print(f"\n发现 widgetName: {widget_matches[:10]}")

    except Exception as e:
        print(f"方案C 失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("调试结束")
    print("=" * 60)


if __name__ == "__main__":
    main()
