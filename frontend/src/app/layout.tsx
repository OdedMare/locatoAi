import type { Metadata } from "next";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "LocatoAI — שאילתות גיאוגרפיות חכמות",
  description: "שאלו שאלות גיאוגרפיות בשפה טבעית",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="he" dir="rtl">
      <body>{children}</body>
    </html>
  );
}
