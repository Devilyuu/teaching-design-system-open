"""The teacher's own lines in the outline: office, phone, biography.

The name is not here on purpose -- it belongs to the account the admin
imported from the roster, and one spelling of it has to hold across the
account list, the course record and every exported document.
"""

from datetime import datetime, timezone

from sqlmodel import Session

from app.models import TeacherProfile, User

REQUIRED_FIELDS = (
    ("office_location", "办公地点"),
    ("phone", "联系电话"),
    ("bio", "教师简介"),
)


class TeacherProfileError(ValueError):
    pass


def get_profile(session: Session, user_id: int | None) -> TeacherProfile | None:
    if user_id is None:
        return None
    return session.get(TeacherProfile, user_id)


def is_complete(profile: TeacherProfile | None) -> bool:
    return profile is not None and all(getattr(profile, field).strip() for field, _ in REQUIRED_FIELDS)


def save_profile(session: Session, user: User, office_location: str, phone: str, bio: str) -> TeacherProfile:
    values = {
        "office_location": " ".join(office_location.split()),
        "phone": " ".join(phone.split()),
        # Paragraph breaks in the biography are the teacher's; only trailing
        # blank lines go.
        "bio": "\n".join(line.rstrip() for line in bio.strip().splitlines()),
    }
    missing = [label for field, label in REQUIRED_FIELDS if not values[field].strip()]
    if missing:
        raise TeacherProfileError("请填写" + "、".join(missing) + "，课程实施大纲的「教师信息」一节会直接使用这些内容")
    assert user.id is not None
    profile = session.get(TeacherProfile, user.id)
    if profile is None:
        profile = TeacherProfile(user_id=user.id)
    for field, value in values.items():
        setattr(profile, field, value)
    profile.updated_at = datetime.now(timezone.utc)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def outline_teacher_lines(profile: TeacherProfile | None, name: str) -> dict[str, str]:
    """The 「教师信息」 lines the outline template leaves blank, by label.

    Without a profile only the name is written; the other lines stay blank
    for the teacher rather than being invented.
    """
    lines = {"教师姓名": name}
    if profile is not None:
        lines.update({
            "办公地点": profile.office_location,
            "联系电话": profile.phone,
            "教师简介": profile.bio,
        })
    return {label: value for label, value in lines.items() if value.strip()}
