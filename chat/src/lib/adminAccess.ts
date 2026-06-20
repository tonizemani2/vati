import { authEnabled, resolveCaller } from "@/lib/auth";

const COOKIE = "vati_admin_pin";
const MAX_AGE_SECONDS = 60 * 60 * 24 * 30;

export async function requireAdminAccess(request: Request) {
  const caller = await resolveCaller(request);
  const localDevOpen = !authEnabled() && process.env.NODE_ENV !== "production";
  const allowed = localDevOpen || (await hasValidAdminPin(request));
  return { caller, allowed };
}

export async function validateAdminPin(pin: string) {
  return pin.trim() === adminPin();
}

export async function adminPinCookie() {
  const issued = Math.floor(Date.now() / 1000);
  const sig = await signPinSession(issued);
  return `${COOKIE}=${issued}.${sig}; Path=/; Max-Age=${MAX_AGE_SECONDS}; HttpOnly; SameSite=Lax; Secure`;
}

async function hasValidAdminPin(request: Request) {
  const value = readCookie(request, COOKIE);
  if (!value) return false;
  const [issuedRaw, sig] = value.split(".");
  const issued = Number(issuedRaw);
  if (!Number.isFinite(issued) || !sig) return false;
  const age = Math.floor(Date.now() / 1000) - issued;
  if (age < 0 || age > MAX_AGE_SECONDS) return false;
  return sig === (await signPinSession(issued));
}

async function signPinSession(issued: number) {
  return sha256Hex(`${issued}|${adminPin()}|${adminSecret()}`);
}

function adminPin() {
  return process.env.VATI_ADMIN_PIN || "258036";
}

function adminSecret() {
  return (
    process.env.VATI_ADMIN_PIN_SECRET ||
    process.env.CLERK_SECRET_KEY ||
    process.env.NEON_AUTH_COOKIE_SECRET ||
    process.env.DEEPSEEK_API_KEY ||
    "local-admin-pin-secret"
  );
}

function readCookie(req: Request, name: string): string | null {
  const raw = req.headers.get("cookie") ?? "";
  const m = raw.match(new RegExp(`(?:^|;\\s*)${name}=([^;]+)`));
  return m ? decodeURIComponent(m[1]) : null;
}

async function sha256Hex(s: string): Promise<string> {
  const data = new TextEncoder().encode(s);
  const buf = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
