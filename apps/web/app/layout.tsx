import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PdfForms",
  description:
    "Fill, flatten and validate PDF AcroForms online from JSON, FDF or XFDF with appearance regeneration and field inspection.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
