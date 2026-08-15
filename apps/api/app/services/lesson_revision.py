from app.models import AiModelConfig
from app.services.lesson_evidence import LessonEvidence
from app.services.openai_compatible import OpenAICompatibleClient


REVISION_FIELDS = {
    "teaching_goals",
    "key_points",
    "difficult_points",
    "teaching_preparation",
    "teaching_process",
    "summary",
    "homework",
}


class LessonRevisionError(ValueError):
    pass


def generate_revision_candidate_text(
    config: AiModelConfig,
    evidence: LessonEvidence,
    field_name: str,
    current_content: str,
    instruction: str,
) -> str:
    if field_name not in REVISION_FIELDS:
        raise LessonRevisionError("不支持重新生成该字段")
    payload = OpenAICompatibleClient(config).generate_json(
        "你是高职院校教学设计助手。只改写指定栏目，不得创造或改写课程目标和能力代码。返回 JSON 对象。",
        {
            "evidence": evidence.to_prompt_payload(),
            "field_name": field_name,
            "current_content": current_content,
            "teacher_instruction": instruction,
            "response_schema": {"proposed_content": "string"},
        },
    )
    proposed = payload.get("proposed_content")
    if not isinstance(proposed, str) or not proposed.strip():
        raise LessonRevisionError("模型未返回有效的候选内容")
    return proposed.strip()
