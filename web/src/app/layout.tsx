import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "부자뚱",
  description: "정명지수 공동 자산 관리",
  appleWebApp: {
    capable: true,
    title: "부자뚱",
    statusBarStyle: "default",
  },
};

/** Prevent iOS Safari auto-zoom on input focus (font < 16px). */
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
  interactiveWidget: "resizes-content",
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
