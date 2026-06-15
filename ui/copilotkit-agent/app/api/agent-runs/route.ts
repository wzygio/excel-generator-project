import { spawn } from "child_process";
import path from "path";
import { NextRequest, NextResponse } from "next/server";

type BridgePayload = {
  action?: string;
  goal?: string;
  query?: string;
  runtime?: string;
  run_id?: string;
  spec_path?: string;
  record_id?: string;
  options?: Record<string, unknown>;
};

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const payload = (await req.json()) as BridgePayload;
  const action = String(payload.action || "create_and_run");

  try {
    const result = await runBridge({ ...payload, action });
    return NextResponse.json(result, { status: result.success === false ? 502 : 200 });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      {
        success: false,
        summary: message,
        artifacts: [],
        data: {},
        warnings: [],
        error: {
          code: "agent_runs_api.bridge_failed",
          message,
          recoverable: true,
          details: {},
        },
        memory_updates: [],
      },
      { status: 500 },
    );
  }
}

function runBridge(payload: BridgePayload): Promise<Record<string, any>> {
  const workspace = process.env.YIELD_REPORT_WORKSPACE
    ? path.resolve(process.env.YIELD_REPORT_WORKSPACE)
    : path.resolve(process.cwd(), "..", "..");
  const uvCommand = process.env.YIELD_REPORT_UV_COMMAND || "uv";
  const bridgePath = path.join(workspace, "scripts", "agent_workbench_bridge.py");

  return new Promise((resolve, reject) => {
    const child = spawn(uvCommand, ["run", "python", bridgePath], {
      cwd: workspace,
      env: {
        ...process.env,
        PYTHONUTF8: "1",
        PYTHONIOENCODING: "utf-8",
      },
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
    });

    let stdout = "";
    let stderr = "";
    const timeout = setTimeout(() => {
      child.kill();
      reject(new Error("Agent run timed out after 20 minutes"));
    }, 20 * 60 * 1000);

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
    child.on("close", (code) => {
      clearTimeout(timeout);
      const raw = stdout.trim();
      if (!raw) {
        reject(new Error(stderr.trim() || `Bridge exited with code ${code}`));
        return;
      }

      try {
        const parsed = JSON.parse(raw) as Record<string, any>;
        if (stderr.trim()) {
          parsed.diagnostics = {
            ...((parsed.diagnostics as Record<string, unknown> | undefined) || {}),
            stderr: stderr.trim(),
          };
        }
        resolve(parsed);
      } catch (error) {
        reject(
          new Error(
            `Bridge returned invalid JSON. stdout=${raw.slice(0, 1000)} stderr=${stderr.slice(0, 1000)}`,
          ),
        );
      }
    });

    child.stdin.write(JSON.stringify(payload));
    child.stdin.end();
  });
}
