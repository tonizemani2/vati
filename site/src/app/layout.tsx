import type { Metadata } from "next";
import "./globals.css";

const DESC =
  "Vaticinus reads millions of research papers, trade flows, and supply records to forecast where scarcity moves next. A deep-research engine and a forecasting model we train ourselves. Every call gets a date, a kill-criterion, and a score in public.";

const TITLE = "Vaticinus: forecasting where scarcity moves next";

export const metadata: Metadata = {
  title: TITLE,
  description: DESC,
  openGraph: {
    title: TITLE,
    description: DESC,
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESC,
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
