import json
from urllib.parse import urlparse

import httpx

from app.models import AiModelConfig
from app.services.openai_compatible import failure_reason, response_json
from app.services.secret_store import decrypt_secret


class AiModelConnectionError(RuntimeError):
    pass


def validate_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("模型接口地址必须是有效的 HTTP 或 HTTPS 地址")
    return normalized


def test_model_connection(config: AiModelConfig) -> None:
    key = decrypt_secret(config.encrypted_api_key)
    try:
        response = httpx.post(
            f"{config.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": config.model_name,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "Return a JSON object only."},
                    {"role": "user", "content": json.dumps({"ping": True})},
                ],
                "max_tokens": 256,
            },
            timeout=20,
        )
        response.raise_for_status()
        content = response_json(response)["choices"][0]["message"]["content"]
        if not isinstance(json.loads(content), dict):
            raise AiModelConnectionError("模型连接测试失败：返回的内容不是 JSON 对象")
    except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AiModelConnectionError(f"模型连接测试失败：{failure_reason(exc, key)}") from exc
