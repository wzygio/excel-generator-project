"""
download_reports.py: 直接运行后端程序下载两个 FineReport 报表到 resources 文件夹

使用方式:
    uv run python scripts/download_reports.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("download_reports")

# 抑制 requests 库的详细日志
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)


def main():
    print("=" * 60)
    print("[FineReport] 报表下载器")
    print("=" * 60)

    # Step 1: 读取产品型号列表
    print("\n[1/4] 读取产品型号列表...")
    try:
        from yield_report.yield_report.infrastructure.product_models import (
            extract_product_models,
        )
        models = extract_product_models()
        print(f"    [OK] 共读取到 {len(models)} 个产品型号")
        print(f"    型号示例: {models[:3]}...")
    except Exception as e:
        print(f"    [WARN] 读取产品型号失败: {e}")
        print("    将使用空列表（不筛选产品型号）")
        models = []

    # Step 2: 下载 V3良率及不良率By月周天汇总报表
    print("\n[2/4] 下载 V3良率及不良率By月周天汇总报表...")
    try:
        from yield_report.yield_report.infrastructure.finereport_client import (
            FinereportClient,
            FineReportConnectionError,
            FineReportDownloadError,
        )

        client = FinereportClient()
        result1 = client.download_daily_yield_report(
            product_models=models if models else None,
        )
        print(f"    [OK] 下载成功: {result1}")
    except FineReportConnectionError as e:
        print(f"    [ERR] 连接失败: {e}")
        print("    请检查 .env 中的 FINEREPORT_* 配置")
        # 如果是认证问题，仍然尝试下载批次报表（可能共享同一个 Session）
        client = None
    except FineReportDownloadError as e:
        print(f"    [ERR] 下载失败: {e}")
        client = None
    except Exception as e:
        print(f"    [ERR] 未知错误: {e}")
        import traceback
        traceback.print_exc()
        client = None

    # Step 3: 下载 V3良率及不良率By批次汇总报表
    print("\n[3/4] 下载 V3良率及不良率By批次汇总报表...")
    try:
        if client is None:
            # 重新创建客户端（如果上一步失败）
            from yield_report.yield_report.infrastructure.finereport_client import (
                FinereportClient,
            )
            client = FinereportClient()
        result2 = client.download_batch_yield_report(
            product_models=models if models else None,
        )
        print(f"    [OK] 下载成功: {result2}")
    except Exception as e:
        print(f"    [ERR] 下载失败: {e}")
        import traceback
        traceback.print_exc()

    # Step 4: 验证结果
    print("\n[4/4] 验证下载结果...")
    resources_dir = project_root / "resources"
    if resources_dir.exists():
        files = list(resources_dir.glob("*.xlsx"))
        for f in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True):
            size_kb = f.stat().st_size / 1024
            print(f"    [FILE] {f.name}  ({size_kb:.1f} KB)")
    else:
        print(f"    [ERR] resources/ 目录不存在")

    print("\n" + "=" * 60)
    print("[OK] 下载流程结束")
    print("=" * 60)


if __name__ == "__main__":
    main()
