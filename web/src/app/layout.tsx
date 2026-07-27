import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "부자뚱",
  description: "부부 공동 자산 관리",
  appleWebApp: {
    capable: true,
    title: "부자뚱",
    statusBarStyle: "default",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <head>
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css"
        />
      </head>
      <body className="min-h-dvh bg-canvas font-sans text-ink antialiased">
        {children}
      </body>
    </html>
  );
}
