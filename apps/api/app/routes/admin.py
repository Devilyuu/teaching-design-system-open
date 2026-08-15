from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import get_current_user, hash_password, require_admin, user_major_ids
from app.db import get_session
from app.models import Major, User, UserMajorLink
from app.schemas import MajorCreate, MajorRead, PasswordReset, StatusResponse, UserCreate, UserRead

admin_router = APIRouter(prefix="/admin", tags=["admin"])
public_router = APIRouter(tags=["majors"])


@admin_router.post("/majors", response_model=MajorRead)
def create_major(
    payload: MajorCreate,
    _: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> Major:
    major = Major(**payload.model_dump())
    session.add(major)
    session.commit()
    session.refresh(major)
    return major


@admin_router.get("/majors", response_model=list[MajorRead])
def list_admin_majors(
    _: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> list[Major]:
    return session.exec(select(Major).order_by(Major.name)).all()


@admin_router.post("/users", response_model=UserRead)
def create_user(
    payload: UserCreate,
    _: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> UserRead:
    existing = session.exec(select(User).where(User.employee_no == payload.employee_no)).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Employee number already exists")
    if payload.role not in {"admin", "teacher"}:
        raise HTTPException(status_code=400, detail="Unsupported role")
    user = User(
        employee_no=payload.employee_no,
        name=payload.name,
        role=payload.role,
        password_hash=hash_password(payload.password),
        is_active=payload.is_active,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    _replace_user_major_links(user.id or 0, payload.major_ids, session)
    return _user_read(user, session)


@admin_router.get("/users", response_model=list[UserRead])
def list_users(
    _: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> list[UserRead]:
    users = session.exec(select(User).order_by(User.employee_no)).all()
    return [_user_read(user, session) for user in users]


@admin_router.post("/users/{user_id}/password", response_model=StatusResponse)
def reset_user_password(
    user_id: int,
    payload: PasswordReset,
    _: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> StatusResponse:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password(payload.password)
    session.add(user)
    session.commit()
    return StatusResponse(status="ok")


@public_router.get("/majors", response_model=list[MajorRead])
def list_visible_majors(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[Major]:
    query = select(Major).where(Major.is_active == True).order_by(Major.name)  # noqa: E712
    if current_user.role == "admin":
        return session.exec(query).all()
    allowed_ids = user_major_ids(current_user, session)
    if not allowed_ids:
        return []
    return session.exec(query.where(Major.id.in_(allowed_ids))).all()  # type: ignore[union-attr]


def _replace_user_major_links(user_id: int, major_ids: list[int], session: Session) -> None:
    existing = session.exec(select(UserMajorLink).where(UserMajorLink.user_id == user_id)).all()
    for link in existing:
        session.delete(link)
    for major_id in major_ids:
        if session.get(Major, major_id) is None:
            raise HTTPException(status_code=400, detail=f"Major {major_id} not found")
        session.add(UserMajorLink(user_id=user_id, major_id=major_id))
    session.commit()


def _user_read(user: User, session: Session) -> UserRead:
    return UserRead(
        id=user.id or 0,
        employee_no=user.employee_no,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        major_ids=user_major_ids(user, session),
    )
