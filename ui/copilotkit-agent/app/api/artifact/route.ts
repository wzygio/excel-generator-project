import { readFile, stat } from "fs/promises";
import path from "path";
import { NextRequest, NextResponse } from "next/server";

const MIME_BY_EXTENSION: Record<string, string> = {
  ".csv": "text/csv; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
};

export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const rawPath = req.nextUrl.searchParams.get("path");
  if (!rawPath) {
    return NextResponse.json({ success: false, summary: "Missing artifact path" }, { status: 400 });
  }

  const workspace = process.env.YIELD_REPORT_WORKSPACE
    ? path.resolve(process.env.YIELD_REPORT_WORKSPACE)
    : path.resolve(process.cwd(), "..", "..");
  const resolvedPath = path.resolve(rawPath);
  const relativePath = path.relative(workspace, resolvedPath);
  if (relativePath.startsWith("..") || path.isAbsolute(relativePath)) {
    return NextResponse.json({ success: false, summary: "Artifact path is outside workspace" }, { status: 403 });
  }

  try {
    const fileStat = await stat(resolvedPath);
    if (!fileStat.isFile()) {
      return NextResponse.json({ success: false, summary: "Artifact path is not a file" }, { status: 404 });
    }

    const body = await readFile(resolvedPath);
    const filename = path.basename(resolvedPath);
    const extension = path.extname(resolvedPath).toLowerCase();
    return new NextResponse(body, {
      headers: {
        "Content-Type": MIME_BY_EXTENSION[extension] || "application/octet-stream",
        "Content-Disposition": `attachment; filename*=UTF-8''${encodeURIComponent(filename)}`,
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ success: false, summary: message }, { status: 404 });
  }
}
