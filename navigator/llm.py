"""Thin wrapper for structured-JSON calls to Claude."""

import json
import os

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
    """Run one request constrained to `schema`; return (parsed_json, metadata)."""
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


def client():
    return anthropic.Anthropic()
