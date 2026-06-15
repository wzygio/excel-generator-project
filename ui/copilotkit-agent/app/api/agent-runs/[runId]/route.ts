import { spawn } from "child_process";
import path from "path";
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

export async function GET(
  _req: NextRequest,
  context: { params: Promise<{ runId: string }> },
) {
  const { runId } = await context.params;
  try {
    const result = await runBridge({ action: "get_run", run_id: runId });
    return NextResponse.json(result, { status: result.success === false ? 404 : 200 });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ success: false, summary: message }, { status: 500 });
  }
}

function runBridge(payload: Record<string, unknown>): Promise<Record<string, any>> {
  const workspace = process.env.YIELD_REPORT_WORKSPACE
    ? path.resolve(process.env.YIELD_REPORT_WORKSPACE)
    : path.resolve(process.cwd(), "..", "..");
  const uvCommand = process.env.YIELD_REPORT_UV_COMMAND || "uv";
  const bridgePath = path.join(workspace, "scripts", "agent_workbench_bridge.py");

  return new Promise((resolve, reject) => {
    const child = spawn(uvCommand, ["run", "python", bridgePath], {
      cwd: workspace,
      env: { ...process.env, PYTHONUTF8: "1", PYTHONIOENCODING: "utf-8" },
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
    });
    let stdout = "";
    let stderr = "";
    const timeout = setTimeout(() => {
      child.kill();
      reject(new Error("Agent snapshot timed out after 60 seconds"));
    }, 60 * 1000);
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    child.on("error", (error) => {
      clearTimeout(timeout);
      reject(error);
    });
    child.on("close", () => {
      clearTimeout(timeout);
      try {
        const parsed = JSON.parse(stdout.trim()) as Record<string, any>;
        if (stderr.trim()) {
          parsed.diagnostics = { stderr: stderr.trim() };
        }
        resolve(parsed);
      } catch {
        reject(new Error(stderr.trim() || "Bridge returned invalid JSON"));
      }
    });
    child.stdin.write(JSON.stringify(payload));
    child.stdin.end();
  });
}
