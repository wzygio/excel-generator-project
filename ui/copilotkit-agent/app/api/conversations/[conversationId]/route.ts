import { NextRequest, NextResponse } from "next/server";
import {
  listConversations,
  normalizeConversation,
  readConversation,
  saveConversation,
  safeConversationId,
} from "../store";

export const runtime = "nodejs";

export async function GET(
  _req: NextRequest,
  context: { params: Promise<{ conversationId: string }> },
) {
  const { conversationId } = await context.params;
  try {
    const conversation = await readConversation(conversationId);
    return NextResponse.json({ success: true, conversation });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ success: false, summary: message }, { status: 404 });
  }
}

export async function PUT(
  req: NextRequest,
  context: { params: Promise<{ conversationId: string }> },
) {
  const { conversationId } = await context.params;
  try {
    const safeId = safeConversationId(conversationId);
    const body = (await req.json()) as Record<string, unknown>;
    const payload =
      body.conversation && typeof body.conversation === "object"
        ? (body.conversation as Record<string, unknown>)
        : body;
    const conversation = normalizeConversation({ ...payload, id: safeId });
    const saved = await saveConversation(conversation);
    const conversations = await listConversations();
    return NextResponse.json({ success: true, conversation: saved, conversations });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ success: false, summary: message }, { status: 400 });
  }
}
