"""Lightweight AI client for the asset pipeline — reuses the same free providers."""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

# Same provider config as server.py
AI_PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "key_env": "GROQ_API_KEY",
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "default_model": "qwen-3-235b-a22b-instruct-2507",
        "key_env": "CEREBRAS_API_KEY",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.5-flash",
        "key_env": "GEMINI_API_KEY",
    },
    "ollama": {
        "base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434") + "/v1",
        "default_model": "llama3.1",
        "key_env": None,
    },
}

VISION_PROVIDERS = {"gemini", "openai"}


def detect_provider() -> tuple[str | None, str | None]:
    """Auto-detect best available free provider. Returns (name, api_key)."""
    explicit = os.environ.get("AI_PROVIDER", "").strip().lower()
    if explicit and explicit in AI_PROVIDERS:
        prov = AI_PROVIDERS[explicit]
        key_env = prov.get("key_env")
        key = os.environ.get(key_env, "").strip() if key_env else "ollama"
        if key:
            return (explicit, key)

    for name in ["groq", "cerebras", "gemini"]:
        prov = AI_PROVIDERS[name]
        key = os.environ.get(prov["key_env"], "").strip()
        if key:
            return (name, key)

    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key:
        return ("openai", openai_key)

    return (None, None)


def detect_vision_provider() -> tuple[str | None, str | None]:
    """Find a vision-capable provider (Gemini preferred)."""
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key:
        return ("gemini", gemini_key)

    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key:
        return ("openai", openai_key)

    return (None, None)


def _get_client(provider: str | None = None, api_key: str | None = None):
    """Create an OpenAI-compatible client."""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package required: pip install openai")

    if provider is None:
        provider, api_key = detect_provider()
    if not provider or not api_key:
        raise RuntimeError(
            "No AI provider configured. Set GROQ_API_KEY, CEREBRAS_API_KEY, or GEMINI_API_KEY."
        )

    if provider == "openai":
        return OpenAI(api_key=api_key), provider
    elif provider in AI_PROVIDERS:
        prov = AI_PROVIDERS[provider]
        return OpenAI(base_url=prov["base_url"], api_key=api_key), provider
    else:
        raise RuntimeError(f"Unknown provider: {provider}")


def chat(
    messages: list[dict[str, Any]],
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """Send a chat completion request and return the text response."""
    client, prov_name = _get_client(provider)

    if model is None:
        model_env = os.environ.get("AI_MODEL", "").strip()
        model = model_env or AI_PROVIDERS.get(prov_name, {}).get("default_model", "")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        raise RuntimeError(f"AI call failed ({prov_name}/{model}): {e}")


def chat_json(
    messages: list[dict[str, Any]],
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.3,
) -> dict[str, Any]:
    """Chat completion expecting JSON response. Parses and returns dict."""
    text = chat(messages, provider=provider, model=model, temperature=temperature)

    # Extract JSON from markdown code blocks if present
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if json_match:
        text = json_match.group(1)

    # Try to find JSON object in the response
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": "Failed to parse JSON", "raw": text}


def vision_analyze(
    prompt: str,
    image_paths: list[Path | str],
    provider: str | None = None,
    model: str | None = None,
) -> str:
    """Send images to a vision-capable model for analysis."""
    if provider is None:
        provider, api_key = detect_vision_provider()
    else:
        _, api_key = detect_provider()

    if not provider:
        raise RuntimeError(
            "No vision-capable provider. Set GEMINI_API_KEY for free vision analysis."
        )

    # For Gemini via OpenAI-compatible API
    if provider == "gemini":
        return _gemini_vision(prompt, image_paths, api_key, model)

    # For OpenAI vision
    client, _ = _get_client(provider, api_key)
    model = model or "gpt-4o-mini"

    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for img_path in image_paths:
        img_path = Path(img_path)
        if img_path.exists():
            data = base64.b64encode(img_path.read_bytes()).decode()
            ext = img_path.suffix.lstrip(".").lower()
            mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{data}"},
            })

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        max_tokens=2048,
    )
    return response.choices[0].message.content or ""


def _gemini_vision(prompt: str, image_paths: list[Path | str], api_key: str | None, model: str | None) -> str:
    """Call Gemini generateContent API with images."""
    import urllib.request

    api_key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY required for vision analysis")

    model = model or "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    parts: list[dict[str, Any]] = [{"text": prompt}]
    for img_path in image_paths:
        img_path = Path(img_path)
        if img_path.exists():
            data = base64.b64encode(img_path.read_bytes()).decode()
            ext = img_path.suffix.lstrip(".").lower()
            mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")
            parts.append({"inline_data": {"mime_type": mime, "data": data}})

    body = json.dumps({"contents": [{"parts": parts}]}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
        candidates = result.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            text_parts = [p.get("text", "") for p in content.get("parts", [])]
            return "\n".join(text_parts)
        return ""
    except Exception as e:
        raise RuntimeError(f"Gemini vision call failed: {e}")
