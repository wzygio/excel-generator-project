import type { Metadata } from "next";
import type { ReactNode } from "react";
import { CopilotKitProvider } from "@copilotkit/react-core/v2";
import "@copilotkit/react-core/v2/styles.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "良率日报 Agent 工作台",
  description: "CopilotKit Agent UI for the yield-report workspace.",
  icons: {
    icon: "/icon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>
        <CopilotKitProvider runtimeUrl="/api/copilotkit" useSingleEndpoint>
          {children}
        </CopilotKitProvider>
      </body>
    </html>
  );
}
