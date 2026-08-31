"""Minimal client for any OpenAI-compatible /chat/completions endpoint
(ollama, llama.cpp server, LM Studio, vLLM, Anthropic's compat layer, ...)."""

import os

import requests


def chat(base_url, model, messages, api_key=None, temperature=0.7,
         max_tokens=2048, timeout=600):
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def api_key_from(env_name):
    return os.environ.get(env_name) if env_name else None
