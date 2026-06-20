"use client";

// Sidebar account row. Signed out -> Sign in / Sign up (Clerk modal, so no dedicated
// /sign-in routes needed). Signed in -> Clerk's UserButton (avatar + account menu).
// Gated on the publishable key so it only mounts when the layout mounted <ClerkProvider>;
// with no Clerk keys (local dev) the app runs open as 'anon' and this renders nothing.
import { Show, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
import { LogIn } from "lucide-react";

const authOn = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);

export function Account() {
  if (!authOn) return null;
  return (
    <div className="mt-1">
      <Show when="signed-out">
        <div className="flex flex-col gap-0.5">
          <SignInButton mode="modal">
            <button className="flex w-full items-center gap-2.5 rounded-[10px] px-[10px] py-[7px] text-left text-[14px] text-[var(--ink)] transition-colors hover:bg-[var(--surface-hover)]">
              <span className="flex h-5 w-5 items-center justify-center">
                <LogIn size={18} strokeWidth={1.8} />
              </span>
              <span className="truncate">Sign in</span>
            </button>
          </SignInButton>
          <SignUpButton mode="modal">
            <button className="flex w-full items-center justify-center rounded-[10px] bg-[var(--brand)] px-[10px] py-[7px] text-[14px] font-medium text-white transition-opacity hover:opacity-90">
              Create account
            </button>
          </SignUpButton>
        </div>
      </Show>
      <Show when="signed-in">
        <div className="flex items-center gap-2.5 rounded-[10px] px-[10px] py-[7px]">
          <UserButton
            appearance={{ elements: { avatarBox: "h-6 w-6" } }}
            showName
          />
        </div>
      </Show>
    </div>
  );
}
