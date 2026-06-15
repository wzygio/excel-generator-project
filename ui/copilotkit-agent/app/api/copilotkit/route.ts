import {
  CopilotRuntime,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { BuiltInAgent } from "@copilotkit/runtime/v2";
import { createOpenAICompatible } from "@ai-sdk/openai-compatible";
import fs from "node:fs";
import path from "node:path";
import { NextRequest } from "next/server";

const DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1";
const DEFAULT_DEEPSEEK_MODEL = "deepseek-chat";

function loadRootEnv() {
  const envPaths = [
    path.resolve(process.cwd(), ".env"),
    path.resolve(process.cwd(), "..", "..", ".env"),
  ];

  for (const envPath of envPaths) {
    if (!fs.existsSync(envPath)) {
      continue;
    }

    const content = fs.readFileSync(envPath, "utf8");

    for (const line of content.split(/\r?\n/)) {
      const match = line.match(/^\s*(?:export\s+)?([\w.-]+)\s*=\s*(.*)?\s*$/);
      if (!match) {
        continue;
      }

      const [, key, rawValue = ""] = match;
      const value = rawValue.trim().replace(/^(['"])(.*)\1$/, "$2");

      if (process.env[key] === undefined) {
        process.env[key] = value;
      }
    }
  }
}

function normalizeDeepSeekBaseURL(value: string | undefined) {
  const baseURL = (value || DEFAULT_DEEPSEEK_BASE_URL).trim().replace(/\/+$/, "");
  return baseURL.endsWith("/v1") ? baseURL : `${baseURL}/v1`;
}

function resolveDeepSeekModel() {
  const model = (process.env.DEEPSEEK_MODEL || DEFAULT_DEEPSEEK_MODEL).trim();
  return model.replace(/^deepseek[:/]/i, "");
}

loadRootEnv();

const deepSeekApiKey = process.env.DEEPSEEK_API_KEY;

if (!deepSeekApiKey) {
  throw new Error("DEEPSEEK_API_KEY is missing. Add it to the repository root .env file.");
}

const deepseek = createOpenAICompatible({
  name: "deepseek",
  apiKey: deepSeekApiKey,
  baseURL: normalizeDeepSeekBaseURL(process.env.DEEPSEEK_BASE_URL),
});

const builtInAgent = new BuiltInAgent({
  model: deepseek.chatModel(resolveDeepSeekModel()),
  prompt:
    "你是良率日报 Agent 工作台的中文助手，当前服务端 LLM provider 使用 DeepSeek API。回答应聚焦报表下载、数据分析、日报生成和项目工作流，不要声称自己来自其他模型厂商。",
});

const runtime = new CopilotRuntime({
  agents: {
    default: builtInAgent,
  },
});

export const POST = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    endpoint: "/api/copilotkit",
  });

  return handleRequest(req);
};
