from collections.abc import Sequence
from dataclasses import dataclass

from app.models import AbilityIndicator, CourseGoal


@dataclass(frozen=True)
class IndicatorReviewData:
    code: str
    category: str
    group_code: str
    description: str


@dataclass(frozen=True)
class GoalReviewData:
    code: str
    description: str
    ability_codes: list[str]
    indicators: list[IndicatorReviewData]
    unknown_codes: list[str]


@dataclass(frozen=True)
class SourceReviewData:
    goals: list[GoalReviewData]
    indicators_count: int
    unknown_codes: list[str]
    can_confirm: bool
    confirmed: bool


def build_source_review(
    goals: Sequence[CourseGoal],
    indicators: Sequence[AbilityIndicator],
    confirmed: bool,
) -> SourceReviewData:
    indicators_by_code = {indicator.code: indicator for indicator in indicators}
    goal_reviews: list[GoalReviewData] = []
    all_unknown_codes: list[str] = []

    for goal in goals:
        ability_codes = goal.ability_codes.split()
        matched: list[IndicatorReviewData] = []
        unknown_codes: list[str] = []
        for code in ability_codes:
            indicator = indicators_by_code.get(code)
            if indicator is None:
                if code not in unknown_codes:
                    unknown_codes.append(code)
                if code not in all_unknown_codes:
                    all_unknown_codes.append(code)
                continue
            matched.append(
                IndicatorReviewData(
                    code=indicator.code,
                    category=indicator.category,
                    group_code=indicator.group_code,
                    description=indicator.description,
                )
            )
        goal_reviews.append(
            GoalReviewData(
                code=goal.code,
                description=goal.description,
                ability_codes=ability_codes,
                indicators=matched,
                unknown_codes=unknown_codes,
            )
        )

    can_confirm = bool(goals) and bool(indicators) and not all_unknown_codes
    return SourceReviewData(
        goals=goal_reviews,
        indicators_count=len(indicators),
        unknown_codes=all_unknown_codes,
        can_confirm=can_confirm,
        confirmed=confirmed and can_confirm,
    )
