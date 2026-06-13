import type { Metadata } from "next";
import "./globals.css";

const DESC =
  "Vaticinus is a leak-free forecasting instrument. Vati calls where scarcity and value move next, locks each call to a dated metric, and grades itself in public against a record you can check.";

const TITLE = "Vaticinus: forecasts that grade themselves";

export const metadata: Metadata = {
  title: TITLE,
  description: DESC,
  icons: {
    icon: "/images/689073a51834398fcd983a0f_favicon.png",
    apple: "/images/689073a8ce04467464065e9a_webclip.png",
  },
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
