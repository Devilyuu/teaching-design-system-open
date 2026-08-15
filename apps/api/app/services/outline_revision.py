import json

from pydantic import BaseModel, Field, ValidationError

from app.models import AiModelConfig, OutlineRow
from app.services.openai_compatible import OpenAICompatibleClient


SYSTEM_PROMPT = """你是高职院校课程实施大纲优化助手。只能优化请求指定的字段，保持课次边界和课程依据不变。返回一个 JSON 对象。"""


class OutlineRevisionError(ValueError):
    pass


class RevisionPayload(BaseModel):
    topic: str | None = Field(default=None, min_length=1, max_length=500)
    teaching_content: str | None = Field(default=None, min_length=1, max_length=10000)
    teaching_methods: str | None = Field(default=None, min_length=1, max_length=5000)
    ideological_point: str | None = Field(default=None, min_length=1, max_length=5000)
    pre_task: str | None = Field(default=None, min_length=1, max_length=5000)
    in_class_task: str | None = Field(default=None, min_length=1, max_length=5000)
    post_task: str | None = Field(default=None, min_length=1, max_length=5000)


def _row_payload(row: OutlineRow | None) -> dict | None:
    if row is None:
        return None
    return {"session_no": row.session_no, "topic": row.topic, "teaching_content": row.teaching_content}


def generate_outline_revision(
    config: AiModelConfig,
    row: OutlineRow,
    previous_row: OutlineRow | None,
    next_row: OutlineRow | None,
    field_name: str,
    instruction: str,
    client_factory=OpenAICompatibleClient,
) -> str:
    payload = client_factory(config).generate_json(
        SYSTEM_PROMPT,
        {
            "field_name": field_name,
            "instruction": instruction,
            "current": row.model_dump(exclude={"id", "task_id", "updated_at"}),
            "previous": _row_payload(previous_row),
            "next": _row_payload(next_row),
        },
    )
    try:
        parsed = RevisionPayload.model_validate(payload)
    except ValidationError as exc:
        raise OutlineRevisionError("AI 返回的局部优化内容结构无效") from exc
    fields_by_scope = {
        "topic": ["topic"],
        "teaching_content": ["teaching_content"],
        "teaching_methods": ["teaching_methods"],
        "tasks": ["pre_task", "in_class_task", "post_task"],
        "all": ["topic", "teaching_content", "ideological_point", "teaching_methods", "pre_task", "in_class_task", "post_task"],
    }
    fields = fields_by_scope[field_name]
    values = {field: getattr(parsed, field) for field in fields}
    if any(not value for value in values.values()):
        raise OutlineRevisionError("AI 返回的局部优化内容缺少必填字段")
    if len(fields) == 1:
        return str(values[fields[0]]).strip()
    return json.dumps(values, ensure_ascii=False)
