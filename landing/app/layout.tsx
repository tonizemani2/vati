import type { Metadata } from "next";
import { Inter, Hanken_Grotesk, Geist_Mono } from "next/font/google";
import "./globals.css";

// Body / UI typeface.
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

// Display face — light geometric grotesque, stands in for KMR Apparat.
const display = Hanken_Grotesk({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
});

// Mono — numbers, spec tags, code.
const mono = Geist_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

const title = "Vaticinus, a forecasting research lab in Berlin";
const description =
  "Vaticinus is a Berlin research lab building Vati, an 8B forecasting model fine-tuned to call where scarcity and value go next before the market prices it in. Live on the Metaculus Cup, built to lead the bot field on ForecastBench, and graded in public on a leak-free record.";

export const metadata: Metadata = {
  metadataBase: new URL("https://vaticinus.com"),
  title,
  description,
  openGraph: {
    title,
    description,
    url: "https://vaticinus.com",
    siteName: "Vaticinus",
    images: [{ url: "/images/og.webp", width: 1200, height: 630 }],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: ["/images/og.webp"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${inter.variable} ${display.variable} ${mono.variable} antialiased`}>
      <body>{children}</body>
    </html>
  );
}
