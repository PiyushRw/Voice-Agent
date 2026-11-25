import json
import os
import httpx
from ..agents.prompts import SYSTEM

def ask(payload, system=SYSTEM):
    messages = [{"role":"system","content":system},
                {"role":"user","content":json.dumps(payload,ensure_ascii=False)}]
    providers = (
        ("GROQ_API_KEY","GROQ_LLM_MODEL","openai/gpt-oss-120b","https://api.groq.com/openai/v1/chat/completions"),
        ("GOOGLE_API_KEY","GEMINI_MODEL","gemini-2.5-flash","https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"),
    )
    for key, model, default, endpoint in providers:
        if not os.getenv(key):
            continue
        try:
            response = httpx.post(endpoint, headers={"Authorization":f"Bearer {os.environ[key]}"}, json={
                "messages":messages,"model":os.getenv(model) or default,
                "response_format":{"type":"json_object"}}, timeout=15)
            response.raise_for_status()
            result = json.loads(response.json()["choices"][0]["message"]["content"])
            if isinstance(result, dict):
                return result
        except (httpx.HTTPError, KeyError, ValueError, TypeError, IndexError):
            continue
    return {}
