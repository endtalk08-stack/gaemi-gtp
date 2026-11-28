"""Read-only check for required AI test environment variables.

This script is intended to run through the existing DigitalOcean gateway's
'run' operation. It reports presence/state only and never prints secret values.
"""
from __future__ import annotations

import json
import os
from collections.abc import Mapping


def build_diagnostic(environ: Mapping[str, str] | None = None) -> dict[str, object]:
    env = os.environ if environ is None else environ

    def configured(name: str) -> bool:
        return bool(str(env.get(name, "")).strip())

    enabled_value = str(env.get("AI_TEST_ENABLED", "")).strip().lower()
    if enabled_value in {"1", "true", "yes", "on"}:
        enabled_state = "enabled"
    elif configured("AI_TEST_ENABLED"):
        enabled_state = "disabled"
    else:
        enabled_state = "missing"

    return {
        "AI_TEST_TOKEN": {"configured": configured("AI_TEST_TOKEN")},
        "AI_TEST_ENABLED": {"state": enabled_state},
        "GROQ_API_KEY": {"configured": configured("GROQ_API_KEY")},
    }


def main() -> None:
    result = build_diagnostic()
    print(
        "GAEMI_AI_TEST_ENV_DIAGNOSTIC="
        + json.dumps(result, ensure_ascii=False, sort_keys=True),
        flush=True,
    )


if __name__ == "__main__":
    main()
