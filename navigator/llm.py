"""Thin wrapper for structured-JSON calls to Claude."""

import json
import os
import shutil
import subprocess
import tempfile

import anthropic

from navigator.paths import ROOT

MODEL = "claude-opus-5-5"


def load_env():
    """Read KEY=value lines from .env into the environment (without overriding real env vars)."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#") and value and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


load_env()


class ModelRefusal(RuntimeError):
    pass


def call_json(client, system, prompt, schema, max_tokens=32000, effort="high"):
    """Run one request constrained to `schema`; return (parsed_json, metadata).

    Uses the Claude API when ANTHROPIC_API_KEY is set, otherwise the locally
    logged-in Claude Code CLI in headless mode (same model, same schema).
    """
    if client is None:
        return _call_json_cli(system, prompt, schema)
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        raise ModelRefusal(str(message.stop_details))
    if message.stop_reason == "max_tokens":
        raise RuntimeError(f"output hit max_tokens={max_tokens}")
    text = next(b.text for b in message.content if b.type == "text")
    meta = {
        "model": message.model,
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
        "stop_reason": message.stop_reason,
    }
    return json.loads(text), meta


def _call_json_cli(system, prompt, schema, tries=3):
    cmd = [
        "claude", "-p",
        "--model", MODEL,
        "--output-format", "json",
        "--json-schema", json.dumps(schema),
        "--system-prompt", system,
        "--tools", "",
        "--setting-sources", "",
        "--strict-mcp-config",
        "--no-session-persistence",
    ]
    last_error = None
    for _ in range(tries):
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=tempfile.gettempdir(),
                              timeout=1800)
        try:
            out = json.loads(proc.stdout)
        except json.JSONDecodeError:
            last_error = f"exit {proc.returncode}: {proc.stderr[-500:] or proc.stdout[-500:]}"
            continue
        if out.get("is_error") or out.get("structured_output") is None:
            last_error = f"{out.get('subtype')}: {str(out.get('result'))[:500]}"
            continue
        usage = out.get("usage", {})
        meta = {
            "model": MODEL,
            "backend": "claude-code-cli",
            "input_tokens": usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "stop_reason": out.get("stop_reason"),
        }
        return out["structured_output"], meta
    raise RuntimeError(f"claude CLI call failed: {last_error}")


def client():
    """An API client when a key is configured; None means use the Claude Code CLI."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return anthropic.Anthropic()
    if shutil.which("claude"):
        return None
    raise RuntimeError("Set ANTHROPIC_API_KEY in .env or log in to Claude Code (`claude`).")
