import type { Metadata } from "next";
import { Cinzel, Cormorant_Garamond, Geist } from "next/font/google";
import "./globals.css";

// Inscriptional caps — the ancient register (wordmark, eyebrows).
const cinzel = Cinzel({
  variable: "--font-cinzel",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

// High-contrast old-style serif — the philosophical lines.
const cormorant = Cormorant_Garamond({
  variable: "--font-cormorant",
  subsets: ["latin"],
  weight: ["300", "400", "500"],
  style: ["normal", "italic"],
});

// Clean grotesque — the modern register (small labels, body).
const geist = Geist({
  variable: "--font-geist",
  subsets: ["latin"],
});

const title = "Vaticinus";
const description =
  "An instrument for reading where value moves next. Calibrated, falsifiable, before consensus.";

export const metadata: Metadata = {
  metadataBase: new URL("https://vaticinus.com"),
  title,
  description,
  openGraph: {
    title,
    description,
    url: "https://vaticinus.com",
    siteName: title,
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
    <html
      lang="en"
      className={`${cinzel.variable} ${cormorant.variable} ${geist.variable} antialiased`}
    >
      <body className="grain">{children}</body>
    </html>
  );
}
