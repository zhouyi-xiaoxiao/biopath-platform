#!/usr/bin/env python3
"""Best-effort browser automation to ask GPT-5.2 Pro (extended thinking) on chatgpt.com."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import subprocess
import sys
from pathlib import Path


def run_json(cmd: list[str]) -> dict:
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out)


def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True)


def find_ref(snapshot: dict, *, role: str | None = None, contains: str | None = None) -> str | None:
    refs = snapshot.get("refs") or {}
    needle = (contains or "").lower()
    for ref, info in refs.items():
        if role and info.get("role") != role:
            continue
        name = str(info.get("name", "")).lower()
        if needle and needle not in name:
            continue
        return ref
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", required=True)
    parser.add_argument("--answer", required=True)
    args = parser.parse_args()

    question = Path(args.question).read_text().strip()
    answer_path = Path(args.answer)
    answer_path.parent.mkdir(parents=True, exist_ok=True)

    run(["openclaw", "browser", "start", "--json"])
    run(["openclaw", "browser", "open", "https://chatgpt.com", "--json"])

    snap = run_json(["openclaw", "browser", "snapshot", "--format", "ai", "--json"])
    dump = json.dumps(snap)
    if "Log in" in dump or "Sign up" in dump:
        raise SystemExit("ChatGPT session not logged in. Please login once and rerun.")

    # Try model picker and highest thinking mode when controls exist.
    model_ref = find_ref(snap, contains="gpt")
    if model_ref:
        try:
            run(["openclaw", "browser", "click", model_ref, "--json"])
            snap2 = run_json(["openclaw", "browser", "snapshot", "--format", "ai", "--json"])
            target = (
                find_ref(snap2, contains="gpt-5.2 pro")
                or find_ref(snap2, contains="5.2 pro")
                or find_ref(snap2, contains="pro")
            )
            if target:
                run(["openclaw", "browser", "click", target, "--json"])
        except Exception:
            pass

    think_ref = None
    try:
        snap3 = run_json(["openclaw", "browser", "snapshot", "--format", "ai", "--json"])
        think_ref = (
            find_ref(snap3, contains="extended")
            or find_ref(snap3, contains="deep")
            or find_ref(snap3, contains="thinking")
            or find_ref(snap3, contains="reason")
        )
    except Exception:
        think_ref = None

    if think_ref:
        try:
            run(["openclaw", "browser", "click", think_ref, "--json"])
        except Exception:
            pass

    snap4 = run_json(["openclaw", "browser", "snapshot", "--format", "ai", "--json"])
    box_ref = find_ref(snap4, role="textbox") or find_ref(snap4, role="combobox")
    if not box_ref:
        raise SystemExit("Unable to find message input box on chatgpt.com")

    run(["openclaw", "browser", "type", box_ref, question, "--json"])
    run(["openclaw", "browser", "press", "Enter", "--json"])

    # Wait for generation to settle.
    for _ in range(36):
        has_stop = run_json(
            [
                "openclaw",
                "browser",
                "evaluate",
                "--fn",
                '() => !!document.querySelector("button[aria-label*=\\"Stop\\" i], button[data-testid*=\\"stop\\" i]")',
                "--json",
            ]
        )
        value = has_stop.get("value")
        if not value:
            break
        run(["openclaw", "browser", "wait", "--time", "2", "--json"])

    answer_eval = run_json(
        [
            "openclaw",
            "browser",
            "evaluate",
            "--fn",
            "() => { const nodes=[...document.querySelectorAll(\"[data-message-author-role='assistant']\")]; const n=nodes.at(-1) || [...document.querySelectorAll(\"article\")].at(-1); return n ? n.innerText : \"\"; }",
            "--json",
        ]
    )
    answer_text = str(answer_eval.get("value") or "").strip()

    if not answer_text:
        raise SystemExit("No assistant answer captured from page")

    answer_path.write_text(
        "\n".join(
            [
                f"# Escalation Answer",
                f"- created_at: {datetime.now(timezone.utc).isoformat()}",
                f"- source: chatgpt.com",
                f"- mode_requested: GPT-5.2 Pro Extended Thinking",
                "",
                answer_text,
                "",
            ]
        )
    )
    print(str(answer_path))


if __name__ == "__main__":
    main()
