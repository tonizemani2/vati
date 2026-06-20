# Cloudflare security runbook

The site should not rely on application code as the only control plane. Keep these
Cloudflare controls around the public site and chat app.

## Turnstile for `Work with us`

Create a Cloudflare Turnstile widget for:

- `vaticinus.com`
- `www.vaticinus.com`
- `*.vaticinus.pages.dev`
- `localhost` for local testing, if needed

Set the public site key at build time:

```sh
cd site
NEXT_PUBLIC_TURNSTILE_SITE_KEY="0x..." pnpm dlx pnpm@10.25.0 run build
```

Set the secret on Cloudflare Pages:

```sh
cd site
../chat/node_modules/.bin/wrangler pages secret put TURNSTILE_SECRET_KEY --project-name=vaticinus
```

The browser widget is not trusted by itself. `site/functions/api/contact.ts`
calls Cloudflare Siteverify before sending email when `TURNSTILE_SECRET_KEY` is set.

## WAF custom rules

Create these in Cloudflare dashboard under `Security` -> `WAF` -> `Custom rules`.

Challenge suspicious page views:

```txt
(http.host in {"vaticinus.com" "www.vaticinus.com" "chat.vaticinus.com"} and cf.threat_score ge 10)
```

Action: `Managed Challenge`.

Block obvious WordPress and admin probes:

```txt
(http.host in {"vaticinus.com" "www.vaticinus.com" "chat.vaticinus.com"} and
 http.request.uri.path matches "(?i)^/(wp-admin|wp-login\\.php|xmlrpc\\.php|admin|administrator|phpmyadmin)")
```

Action: `Block`.

Block direct API abuse after a rate limit threshold rather than challenging POSTs:

```txt
(http.host eq "vaticinus.com" and http.request.uri.path eq "/api/contact" and http.request.method eq "POST")
```

Suggested rate limit: 5 requests per 10 minutes per IP. Action: `Block` for 10 minutes.

```txt
(http.host eq "chat.vaticinus.com" and starts_with(http.request.uri.path, "/api/"))
```

Suggested rate limit: 60 requests per 10 minutes per IP. Action: `Block` for 10 minutes.

## Managed protections

Enable the Cloudflare Managed Ruleset and OWASP Core Ruleset for `vaticinus.com`.
If Bot Fight Mode or Super Bot Fight Mode is available on the plan, enable it for the
marketing site and chat app, then watch analytics for false positives.

## Deployment posture

`chat/wrangler.jsonc` sets `workers_dev` to `false`. Keep it that way. The raw
`*.workers.dev` hostname should not remain public, because it can bypass zone-level
rules attached to `chat.vaticinus.com`.
