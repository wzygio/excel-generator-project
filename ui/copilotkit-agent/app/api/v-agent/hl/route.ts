import fs from "node:fs/promises";
import path from "node:path";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST() {
  const messagePath = resolveLatestMessagePath();
  try {
    const message = await fs.readFile(messagePath, "utf8");
    return new NextResponse(message.trim() || emptyMessage(), {
      status: 200,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  } catch (error) {
    const code = typeof error === "object" && error !== null && "code" in error ? error.code : "";
    if (code === "ENOENT") {
      return new NextResponse(emptyMessage(), {
        status: 200,
        headers: { "Content-Type": "text/plain; charset=utf-8" },
      });
    }
    const message = error instanceof Error ? error.message : String(error);
    return new NextResponse(`读取最新 HL 异常通报失败: ${message}`, {
      status: 500,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }
}

function resolveLatestMessagePath() {
  if (process.env.YIELD_REPORT_V_AGENT_LATEST_MESSAGE_PATH) {
    return path.resolve(process.env.YIELD_REPORT_V_AGENT_LATEST_MESSAGE_PATH);
  }
  const workspace = process.env.YIELD_REPORT_WORKSPACE
    ? path.resolve(process.env.YIELD_REPORT_WORKSPACE)
    : path.resolve(process.cwd(), "..", "..");
  return path.join(workspace, "output", "latest_hl_anomaly_message.txt");
}

function emptyMessage() {
  return "暂无可推送的 HL 异常内容。请先在 Agent Workbench 点击异常HL/异常监控生成本地结果。";
}
