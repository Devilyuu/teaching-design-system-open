from dataclasses import dataclass


@dataclass(frozen=True)
class AdjustmentSuggestion:
    suggestion_type: str
    text: str
    suggested_minutes: int
    requires_adjustment: bool


def generate_adjustment_suggestion(
    progress: str,
    mastery: str,
    effect: str,
    note: str,
) -> AdjustmentSuggestion:
    actions: list[str] = []
    kinds: list[str] = []
    minutes = 0

    if progress == "partial":
        actions.append("补讲本次课未完成内容")
        kinds.append("progress")
        minutes = 20
    elif progress == "not_completed":
        actions.append("优先完成本次课遗留内容")
        kinds.append("progress")
        minutes = 40

    if mastery == "average":
        actions.append("安排复习、示范或基础练习")
        kinds.append("mastery")
    elif mastery == "weak":
        actions.append("增加分步示范和基础练习，并降低新任务难度")
        kinds.append("mastery")

    if effect == "needs_adjustment":
        actions.append("调整课堂活动组织方式或降低任务复杂度")
        kinds.append("effect")

    if not actions:
        return AdjustmentSuggestion("none", "本次课正常完成，无需调整下一次课。", 0, False)

    context = f"补充说明：{note.strip()}。" if note.strip() else ""
    return AdjustmentSuggestion(
        "+".join(kinds),
        f"{context}建议" + "；".join(actions) + "。",
        minutes,
        True,
    )


def build_adjustment_block(process: str, reflection_id: int, source_label: str, suggestion: str) -> str:
    start = f"【上次课衔接调整·记录 {reflection_id} 开始】"
    end = f"【上次课衔接调整·记录 {reflection_id} 结束】"
    return f"{start}\n来源：{source_label}\n{suggestion}\n{end}\n{process}"


def remove_adjustment_block(process: str, reflection_id: int) -> str:
    start = f"【上次课衔接调整·记录 {reflection_id} 开始】"
    end = f"【上次课衔接调整·记录 {reflection_id} 结束】"
    before, separator, rest = process.partition(start)
    if not separator:
        return process
    _, end_separator, after = rest.partition(end)
    if not end_separator:
        return process
    return before + after.lstrip("\n")
