// Reusable Resend email sender for Cloudflare Pages Functions.
// Keep email-sending centralised here: any future function (api/*) imports
// `sendEmail` rather than re-implementing the Resend call. The API key lives
// only in the Pages secret RESEND_API_KEY, never in client code or the repo.
//
// Set the secret once:
//   cd site && wrangler pages secret put RESEND_API_KEY --project-name=vaticinus

export type EmailInput = {
  from: string;
  to: string | string[];
  subject: string;
  text?: string;
  html?: string;
  replyTo?: string;
};

export type SendResult = { ok: true; id: string } | { ok: false; error: string };

export async function sendEmail(
  apiKey: string | undefined,
  msg: EmailInput,
): Promise<SendResult> {
  if (!apiKey) return { ok: false, error: "RESEND_API_KEY is not configured" };

  const body: Record<string, unknown> = {
    from: msg.from,
    to: Array.isArray(msg.to) ? msg.to : [msg.to],
    subject: msg.subject,
  };
  if (msg.text) body.text = msg.text;
  if (msg.html) body.html = msg.html;
  if (msg.replyTo) body.reply_to = msg.replyTo;

  let res: Response;
  try {
    res = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
  } catch (e) {
    return { ok: false, error: `network error: ${(e as Error).message}` };
  }

  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    return { ok: false, error: `resend ${res.status}: ${detail.slice(0, 300)}` };
  }

  const data = (await res.json().catch(() => ({}))) as { id?: string };
  return { ok: true, id: data.id ?? "" };
}
