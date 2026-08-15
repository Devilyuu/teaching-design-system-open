from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import require_admin
from app.db import get_session
from app.models import AiModelConfig, User
from app.schemas import AiModelConfigRead, AiModelConfigUpdate, AiModelEnable
from app.services.ai_model_config import AiModelConnectionError, test_model_connection, validate_base_url
from app.services.secret_store import ModelSecretError, encrypt_secret, mask_secret


router = APIRouter(prefix="/admin/ai-model", tags=["admin-ai-model"])


def _find_config(session: Session) -> AiModelConfig | None:
    return session.exec(select(AiModelConfig).order_by(AiModelConfig.id)).first()


def _read_config(config: AiModelConfig | None) -> AiModelConfigRead:
    if config is None:
        return AiModelConfigRead(
            id=None,
            base_url="",
            model_name="",
            api_key_status="未配置",
            enabled=False,
            connection_status="unconfigured",
            last_tested_at=None,
            updated_at=None,
        )
    return AiModelConfigRead(
        id=config.id,
        base_url=config.base_url,
        model_name=config.model_name,
        api_key_status=mask_secret(config.encrypted_api_key),
        enabled=config.enabled,
        connection_status=config.connection_status,
        last_tested_at=config.last_tested_at,
        updated_at=config.updated_at,
    )


@router.get("", response_model=AiModelConfigRead)
def get_ai_model_config(
    _: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> AiModelConfigRead:
    return _read_config(_find_config(session))


@router.put("", response_model=AiModelConfigRead)
def update_ai_model_config(
    payload: AiModelConfigUpdate,
    _: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> AiModelConfigRead:
    config = _find_config(session)
    if config is None and not payload.api_key.strip():
        raise HTTPException(status_code=400, detail="首次配置必须填写 API 密钥")
    try:
        base_url = validate_base_url(payload.base_url)
        encrypted_api_key = (
            encrypt_secret(payload.api_key.strip())
            if payload.api_key.strip()
            else config.encrypted_api_key if config else ""
        )
    except (ValueError, ModelSecretError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if config is None:
        config = AiModelConfig(
            base_url=base_url,
            model_name=payload.model_name.strip(),
            encrypted_api_key=encrypted_api_key,
        )
    else:
        config.base_url = base_url
        config.model_name = payload.model_name.strip()
        config.encrypted_api_key = encrypted_api_key
    config.enabled = False
    config.connection_status = "untested"
    config.last_tested_at = None
    config.updated_at = datetime.now(timezone.utc)
    session.add(config)
    session.commit()
    session.refresh(config)
    return _read_config(config)


@router.post("/test", response_model=AiModelConfigRead)
def test_ai_model_config(
    _: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> AiModelConfigRead:
    config = _find_config(session)
    if config is None:
        raise HTTPException(status_code=404, detail="尚未配置 AI 模型")
    try:
        test_model_connection(config)
    except (AiModelConnectionError, ModelSecretError) as exc:
        config.connection_status = "failed"
        config.enabled = False
        config.last_tested_at = datetime.now(timezone.utc)
        session.add(config)
        session.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    config.connection_status = "connected"
    config.last_tested_at = datetime.now(timezone.utc)
    session.add(config)
    session.commit()
    session.refresh(config)
    return _read_config(config)


@router.post("/enable", response_model=AiModelConfigRead)
def enable_ai_model_config(
    payload: AiModelEnable,
    _: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> AiModelConfigRead:
    config = _find_config(session)
    if config is None:
        raise HTTPException(status_code=404, detail="尚未配置 AI 模型")
    if payload.enabled and config.connection_status != "connected":
        raise HTTPException(status_code=409, detail="请先通过模型连接测试")
    config.enabled = payload.enabled
    config.updated_at = datetime.now(timezone.utc)
    session.add(config)
    session.commit()
    session.refresh(config)
    return _read_config(config)
