# Central chat gaemi / info / pro (pre-membership)

The existing bottom and hero mode pickers are unchanged. A selected mode is
sent as `app_mode` with each central-chat message; the server does not trust
the legacy `role` field when the caller uses the private preview session.

| Mode | Current behavior | AI |
| --- | --- | --- |
| gaemi | Existing stock search, quotes, rankings and stored market-close reading. Unsupported natural-language AI requests get a "switch to info/pro" notice. Verified deterministic previous-day/52-week quote calculations may still run. | Never calls a text-generation model |
| info | Stock-context or general questions | Model 4: Cloudflare Workers AI `@cf/openai/gpt-oss-20b` |
| pro | Stock-context or general questions | Model 3: Groq `qwen/qwen3.8-27b` |

A visitor cannot select an arbitrary `role` to override the server routing.
The independent admin bearer-token `/ai-test` route continues its existing
separate model evaluation behavior.

**Current private-only quota rule:** No artificial 10/day, 5/day or
2/minute cap for the private site chat. The API provider enforces the
account's actual free/project rate and token limits. The numbers displayed
in the administrator model status screen for Groq (30/min, 1,000/day,
8,000 tokens/min, 200,000 tokens/day) are *reference limits* and may
not match the live project quota. Cloudflare's free Workers AI quota
is separate and measured differently; it is not a 1,000-requests/day
guarantee. Existing model 1 (Groq 20B) remains available for news,
and model 2 (Groq 120B) remains assigned to US market-close editorial.
Qwen (model 3) still shares the Groq **organization/project** quota
with models 1/2 even though the chat model is different.

This is **not** a billing hard stop. If either provider account has paid
overages enabled, a successful API call can still incur charges. Keep
the site private. Before allowing public access or members, add
authenticated tier enforcement, shared atomic quota accounting (Redis),
and separate provider spending safeguards.

Existing news, filings, chart/quote handlers and 07:00 US-close worker are
untouched by this change.
