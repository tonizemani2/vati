import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";

export const metadata: Metadata = {
  title: "Vaticinus",
  description:
    "Chat with Vaticinus, a forecasting model that predicts where scarcity moves next. Calibrated, falsifiable, pre-consensus calls with a date, a kill-criterion, and a public score.",
  robots: {
    index: false,
    follow: false,
    nocache: true,
  },
};

// When Clerk is configured (NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY present), wrap the app in the
// Clerk provider so the sign-in UI + session hooks work. Otherwise (local dev with no keys)
// render plain so the app runs open as user 'anon'.
const authOn = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{authOn ? <ClerkProvider>{children}</ClerkProvider> : children}</body>
    </html>
  );
}
