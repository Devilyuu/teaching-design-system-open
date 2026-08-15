from dataclasses import FrozenInstanceError

import pytest

from app.models import AbilityIndicator, CourseGoal
from app.services.source_validation import build_source_review


def test_build_source_review_matches_all_referenced_indicators():
    goals = [
        CourseGoal(
            task_id=1,
            code="M1",
            description="Understand the workflow",
            ability_codes="1-3-4 2-3-4",
        )
    ]
    indicators = [
        AbilityIndicator(
            task_id=1,
            code="1-3-4",
            category="knowledge",
            group_code="1-3",
            description="Explore keyframe production methods",
        ),
        AbilityIndicator(
            task_id=1,
            code="2-3-4",
            category="ability",
            group_code="2-3",
            description="Complete a creative project",
        ),
    ]

    review = build_source_review(goals, indicators, confirmed=True)

    assert review.indicators_count == 2
    assert review.unknown_codes == []
    assert review.can_confirm is True
    assert review.confirmed is True
    assert review.goals[0].ability_codes == ["1-3-4", "2-3-4"]
    assert [item.code for item in review.goals[0].indicators] == ["1-3-4", "2-3-4"]
    assert review.goals[0].indicators[0].description == "Explore keyframe production methods"
    with pytest.raises(FrozenInstanceError):
        review.confirmed = False


def test_build_source_review_deduplicates_unknown_codes_and_cannot_confirm():
    goals = [
        CourseGoal(
            task_id=1,
            code="M1",
            description="Unknown reference",
            ability_codes="9-9-9 9-9-9",
        )
    ]
    indicators = [
        AbilityIndicator(
            task_id=1,
            code="1-3-4",
            category="knowledge",
            group_code="1-3",
            description="Known indicator",
        )
    ]

    review = build_source_review(goals, indicators, confirmed=True)

    assert review.can_confirm is False
    assert review.confirmed is False
    assert review.unknown_codes == ["9-9-9"]
    assert review.goals[0].unknown_codes == ["9-9-9"]
    assert review.goals[0].indicators == []
