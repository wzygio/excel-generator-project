import { NextRequest, NextResponse } from "next/server";
import {
  createConversation,
  listConversations,
  normalizeConversation,
  saveConversation,
} from "./store";

export const runtime = "nodejs";

export async function GET() {
  try {
    const conversations = await listConversations();
    return NextResponse.json({ success: true, conversations });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ success: false, summary: message }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json().catch(() => ({}))) as Record<string, unknown>;
    const conversation =
      body.conversation !== undefined
        ? normalizeConversation(body.conversation)
        : createConversation(String(body.title || "新会话"));
    const saved = await saveConversation(conversation);
    const conversations = await listConversations();
    return NextResponse.json({ success: true, conversation: saved, conversations });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ success: false, summary: message }, { status: 400 });
  }
}
