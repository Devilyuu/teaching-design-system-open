import pytest
from pydantic import ValidationError

from app.models import SessionMaterial
from app.schemas import SessionMaterialGenerate


def test_session_material_is_a_persistent_sqlmodel_table():
    assert SessionMaterial.__tablename__ == "sessionmaterial"
    assert "outline_row_id" in SessionMaterial.model_fields
    assert "owner_user_id" in SessionMaterial.model_fields


def test_generation_request_rejects_invalid_limits():
    with pytest.raises(ValidationError):
        SessionMaterialGenerate(
            material_type="test",
            difficulty="medium",
            estimated_minutes=0,
            question_count=51,
        )
