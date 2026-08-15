import os

from cryptography.fernet import Fernet, InvalidToken


class ModelSecretError(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = os.getenv("MODEL_CONFIG_ENCRYPTION_KEY", "")
    if not key:
        raise ModelSecretError("MODEL_CONFIG_ENCRYPTION_KEY is not configured")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ModelSecretError("MODEL_CONFIG_ENCRYPTION_KEY is invalid") from exc


def encrypt_secret(value: str) -> str:
    if not value:
        raise ModelSecretError("Model API key is required")
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeEncodeError) as exc:
        raise ModelSecretError("Stored model API key cannot be decrypted") from exc


def mask_secret(value: str) -> str:
    return "已配置" if value else "未配置"
