#!/usr/bin/env python3
"""Best-effort browser automation to ask GPT-5.2 Pro (extended thinking) on chatgpt.com."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
import subprocess
import sys
from pathlib import Path


def run_json(cmd: list[str]) -> dict:
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out)


def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True)


def try_send_with_dom(question: str) -> bool:
    fn = f"""
() => {{
  const text = {json.dumps(question)};
  const sendEnter = (el) => {{
    el.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', which: 13, keyCode: 13, bubbles: true }}));
    el.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Enter', code: 'Enter', which: 13, keyCode: 13, bubbles: true }}));
  }};

  const textarea = document.querySelector('textarea');
  if (textarea) {{
    textarea.focus();
    textarea.value = text;
    textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
    sendEnter(textarea);
    return true;
  }}

  const editable = document.querySelector('[contenteditable=\"true\"]');
  if (editable) {{
    editable.focus();
    const sel = window.getSelection();
    if (sel && editable.firstChild) {{
      sel.removeAllRanges();
      const range = document.createRange();
      range.selectNodeContents(editable);
      range.collapse(false);
      sel.addRange(range);
    }}
    document.execCommand('insertText', false, text);
    sendEnter(editable);
    return true;
  }}

  return false;
}}
""".strip()
    result = run_json(["openclaw", "browser", "evaluate", "--fn", fn, "--json"])
    value = result.get("result", result.get("value"))
    return bool(value)


def _iter_snapshot_refs(snapshot: dict):
    # Old CLI shape: {"refs": {"e1": {"role": "button", "name": "..."}}}
    refs = snapshot.get("refs") or {}
    for ref, info in refs.items():
        yield str(ref), str(info.get("role", "")), str(info.get("name", ""))

    # Aria shape: {"nodes": [{"ref":"ax1","role":"button","name":"..."}, ...]}
    nodes = snapshot.get("nodes") or []
    for node in nodes:
        ref = node.get("ref")
        if ref:
            yield str(ref), str(node.get("role", "")), str(node.get("name", ""))

    # AI shape: {"snapshot": "- button \"Name\" [ref=e12] ..."}
    text = snapshot.get("snapshot")
    if isinstance(text, str):
        for line in text.splitlines():
            m_named = re.search(r"-\s*([^\[\"]+?)\s+\"([^\"]*)\"\s+\[ref=([^\]]+)\]", line)
            if m_named:
                role, name, ref = m_named.group(1).strip(), m_named.group(2).strip(), m_named.group(3).strip()
                yield ref, role, name
                continue
            m_unnamed = re.search(r"-\s*([^\[\"]+?)\s+\[ref=([^\]]+)\](?:[^:]*:\s*(.*))?\s*$", line)
            if m_unnamed:
                role = m_unnamed.group(1).strip()
                ref = m_unnamed.group(2).strip()
                name = (m_unnamed.group(3) or "").strip()
                yield ref, role, name


def find_ref(snapshot: dict, *, role: str | None = None, contains: str | None = None) -> str | None:
    want_role = (role or "").strip().lower()
    needle = (contains or "").strip().lower()

    for ref, got_role, name in _iter_snapshot_refs(snapshot):
        got_role_l = got_role.lower()
        name_l = name.lower()
        if want_role and want_role not in got_role_l:
            continue
        if needle and needle not in name_l:
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
    model_ref = find_ref(snap, contains="model selector")
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

    # Ensure Deep Research mode is off (it renders output in an iframe and breaks text capture).
    deep_on_ref = find_ref(snap4, contains="deep research, click to remove")
    if deep_on_ref:
        try:
            run(["openclaw", "browser", "click", deep_on_ref, "--json"])
            snap4 = run_json(["openclaw", "browser", "snapshot", "--format", "ai", "--json"])
        except Exception:
            pass

    box_ref = (
        find_ref(snap4, role="textbox")
        or find_ref(snap4, role="combobox")
        or find_ref(snap4, contains="ask anything")
        or find_ref(snap4, contains="get a detailed report")
        or find_ref(snap4, contains="message chatgpt")
        or find_ref(snap4, contains="send a message")
    )
    send_ref = find_ref(snap4, contains="send prompt") or find_ref(snap4, contains="send")

    sent = False
    if box_ref:
        try:
            run(["openclaw", "browser", "type", box_ref, question, "--submit", "--json"])
            sent = True
        except Exception:
            try:
                run(["openclaw", "browser", "type", box_ref, question, "--json"])
                if send_ref:
                    run(["openclaw", "browser", "click", send_ref, "--json"])
                else:
                    run(["openclaw", "browser", "press", "Enter", "--json"])
                sent = True
            except Exception:
                sent = try_send_with_dom(question)
                if not sent and send_ref:
                    try:
                        run(["openclaw", "browser", "click", send_ref, "--json"])
                        sent = True
                    except Exception:
                        sent = False
    else:
        sent = try_send_with_dom(question)
        if not sent and send_ref:
            try:
                run(["openclaw", "browser", "click", send_ref, "--json"])
                sent = True
            except Exception:
                sent = False

    if not sent:
        raise SystemExit("Failed to send question on chatgpt.com")

    # Wait for generation to settle.
    for _ in range(36):
        has_stop = run_json(
            [
                "openclaw",
                "browser",
                "evaluate",
                "--fn",
                '() => [...document.querySelectorAll("button")].some((b) => /stop/i.test(`${b.getAttribute("aria-label") || ""} ${b.textContent || ""}`) || /stop/i.test(b.getAttribute("data-testid") || ""))',
                "--json",
            ]
        )
        value = has_stop.get("result", has_stop.get("value"))
        if not value:
            break
        run(["openclaw", "browser", "wait", "--time", "2", "--json"])

    answer_eval = run_json(
        [
            "openclaw",
            "browser",
            "evaluate",
            "--fn",
            """() => {
              const clean = (s) => (s || "").trim();
              const fromRole = [...document.querySelectorAll("[data-message-author-role='assistant']")]
                .map((n) => clean(n.innerText))
                .filter(Boolean);
              const fromArticles = [...document.querySelectorAll("article")]
                .map((n) => clean(n.innerText))
                .filter(Boolean);
              const fromMarkdown = [...document.querySelectorAll("[data-testid*='conversation-turn'] .markdown, .prose")]
                .map((n) => clean(n.innerText))
                .filter(Boolean);
              const merged = [...fromRole, ...fromArticles, ...fromMarkdown]
                .filter((s) => s.length > 20 && !/^ChatGPT said:?$/i.test(s));
              if (!merged.length) return "";
              // Prefer the latest substantial answer; fall back to the longest one.
              const latest = merged.at(-1);
              if (latest && latest.length >= 80) return latest;
              return merged.slice().sort((a, b) => b.length - a.length)[0];
            }""",
            "--json",
        ]
    )
    answer_text = str(answer_eval.get("result", answer_eval.get("value")) or "").strip()

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
