# Central chat gaemi / info / pro (pre-membership)

The existing bottom and hero mode pickers are unchanged. A selected mode is
sent as `app_mode` with each central-chat message; the server does not trust
the legacy `role` field when the caller uses the private preview session.

| Mode | Current behavior | AI |
| --- | --- | --- |
| gaemi | Existing stock search, quotes, rankings and stored market-close reading. Unsupported natural-language AI requests get a "switch to info/pro" notice. Verified deterministic previous-day/52-week quote calculations may still run. | Never calls a text-generation model |
| info | Stock-context or general questions | Groq `openai/gpt-oss-20b` |
| pro | Stock-context or general questions | Groq `openai/gpt-oss-120b` |

A visitor cannot select an arbitrary `role` to override the server routing.
The independent admin bearer-token `/ai-test` route continues its existing
separate model evaluation behavior.

**Temporary pre-membership caps:** per running Render process and KST day:
10 info requests, 5 pro requests, and at most 2 AI calls per minute across
the private preview. Requests are counted before calling Groq, including
failed provider calls. These counters reset on restart/redeployment and are
not distributed. They are not billing caps or customer quotas. Actual provider
usage remains controlled by the Groq account. For public signups, add
authenticated account/tier enforcement, a shared atomic quota store (Redis),
anti-abuse measures and a spending budget **before opening AI chat publicly**.

Existing news, filings, chart/quote handlers and 07:00 US-close worker are
untouched by this change.
