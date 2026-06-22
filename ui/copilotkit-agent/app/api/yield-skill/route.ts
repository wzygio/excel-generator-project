import { spawn } from "child_process";
import path from "path";
import { NextRequest, NextResponse } from "next/server";

const VALID_MODULES = new Set(["report_download", "data_analysis", "daily_report", "anomaly_monitor"]);
const VALID_ACTIONS = new Set(["run", "confirm_memory", "reject_memory", "correct_memory"]);

type BridgePayload = {
  module?: string;
  action?: string;
  query?: string;
  record_id?: string;
  options?: Record<string, unknown>;
};

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const payload = (await req.json()) as BridgePayload;
  const moduleName = String(payload.module || "");
  const action = String(payload.action || "run");

  if (!VALID_MODULES.has(moduleName)) {
    return NextResponse.json(
      { success: false, summary: `Unsupported module: ${moduleName}` },
      { status: 400 },
    );
  }

  if (!VALID_ACTIONS.has(action)) {
    return NextResponse.json(
      { success: false, summary: `Unsupported action: ${action}` },
      { status: 400 },
    );
  }

  try {
    const result = await runBridge({ ...payload, module: moduleName, action });
    return NextResponse.json(result, { status: result.success === false ? 502 : 200 });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      {
        success: false,
        skill_name: moduleName,
        summary: message,
        artifacts: [],
        data: {},
        warnings: [],
        error: {
          code: "copilotkit_api.bridge_failed",
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

function runBridge(payload: BridgePayload): Promise<Record<string, unknown>> {
  const workspace = process.env.YIELD_REPORT_WORKSPACE
    ? path.resolve(process.env.YIELD_REPORT_WORKSPACE)
    : path.resolve(process.cwd(), "..", "..");
  const uvCommand = process.env.YIELD_REPORT_UV_COMMAND || "uv";
  const bridgePath = path.join(workspace, "scripts", "copilotkit_skill_bridge.py");

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
      reject(new Error("Skill execution timed out after 15 minutes"));
    }, 15 * 60 * 1000);

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
        const parsed = JSON.parse(raw) as Record<string, unknown>;
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
