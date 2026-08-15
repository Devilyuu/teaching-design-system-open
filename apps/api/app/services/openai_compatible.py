import json

import httpx

from app.models import AiModelConfig
from app.services.secret_store import decrypt_secret


class ModelProviderError(RuntimeError):
    pass


def failure_reason(exc: Exception, secret: str = "") -> str:
    """Name the leg that failed, so a new gateway can be diagnosed from the message.

    Everything used to surface as "模型未返回有效的结构化内容", which once sent an
    investigation after the prompt when the real cause was a 60 second timeout.
    Pointing a fresh OpenAI-compatible endpoint at this needs the opposite: the
    status code, and what usually explains it.
    """
    if isinstance(exc, NotJsonResponse):
        return str(exc)
    if isinstance(exc, httpx.TimeoutException):
        return "请求超时，请确认网关允许单次请求跑满 300 秒"
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        hints = {
            400: "请求被拒绝，常见原因是网关不支持 response_format=json_object",
            401: "鉴权失败，请检查 API Key",
            403: "鉴权被拒绝，请检查 API Key 的权限",
            404: "接口地址不存在，请确认地址是否需要以 /v1 结尾",
            429: "调用频率或额度超限",
        }
        hint = hints.get(status, "服务端错误" if status >= 500 else "请求被拒绝")
        body = _redact(exc.response.text, secret)[:200].strip()
        return f"HTTP {status}：{hint}" + (f"，响应：{body}" if body else "")
    if isinstance(exc, httpx.TransportError):
        return f"无法连接到接口地址（{type(exc).__name__}）"
    if isinstance(exc, KeyError):
        return "响应里没有 choices[0].message.content，可能不是 OpenAI 兼容格式"
    if isinstance(exc, json.JSONDecodeError):
        return "模型返回的内容不是 JSON，可能网关未按 response_format 生效"
    return "模型未返回有效的结构化内容"


def _redact(text: str, secret: str) -> str:
    """A gateway that echoes the request must not put the key in an error message."""
    return text.replace(secret, "***") if secret else text


class NotJsonResponse(ValueError):
    """The body itself is not JSON, which is a different fault from bad content.

    A gateway fronted by a web application answers an unauthenticated call with
    its login page at HTTP 200, so the give-away is the content type, not the
    model's output.
    """

    def __init__(self, response) -> None:
        kind = response.headers.get("content-type", "").split(";")[0].strip() or "未知类型"
        super().__init__(
            f"接口返回的是 {kind} 而不是 JSON，"
            "地址可能指向了网页而不是 API，或请求未通过鉴权被重定向到登录页"
        )


def response_json(response) -> dict:
    try:
        return response.json()
    except ValueError as exc:
        raise NotJsonResponse(response) from exc


class OpenAICompatibleClient:
    def __init__(
        self,
        config: AiModelConfig,
        transport: httpx.BaseTransport | None = None,
        # Generating a whole-course outline in one call runs to several
        # minutes; 60s silently turned that into "模型未返回有效的结构化内容".
        timeout_seconds: float = 300,
    ) -> None:
        self.config = config
        self.transport = transport
        self.timeout_seconds = timeout_seconds

    def generate_json(self, system_prompt: str, user_payload: dict) -> dict:
        key = decrypt_secret(self.config.encrypted_api_key)
        try:
            with httpx.Client(transport=self.transport, timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.config.base_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.config.model_name,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                        ],
                    },
                )
                response.raise_for_status()
                content = response_json(response)["choices"][0]["message"]["content"]
                payload = json.loads(content)
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ModelProviderError(failure_reason(exc, key)) from exc
        if not isinstance(payload, dict):
            raise ModelProviderError("模型返回内容必须是 JSON 对象")
        return payload
