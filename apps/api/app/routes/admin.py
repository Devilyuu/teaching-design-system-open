from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import get_current_user, hash_password, require_admin, user_major_ids
from app.db import get_session
from app.models import Major, User, UserMajorLink
from app.schemas import (
    MajorCreate,
    MajorRead,
    PasswordReset,
    StatusResponse,
    UserBatchCreate,
    UserBatchResult,
    UserCreate,
    UserRead,
    UserUpdate,
)

admin_router = APIRouter(prefix="/admin", tags=["admin"])
public_router = APIRouter(tags=["majors"])

MIN_PASSWORD_LENGTH = 8


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
    employee_no = payload.employee_no.strip()
    name = payload.name.strip()
    if not employee_no or not name:
        raise HTTPException(status_code=400, detail="工号和姓名都不能为空")
    if _find_by_employee_no(employee_no, session) is not None:
        raise HTTPException(status_code=400, detail=f"工号 {employee_no} 已有账号，如需重置密码请在账号列表里操作")
    if payload.role not in {"admin", "teacher"}:
        raise HTTPException(status_code=400, detail="角色只能是 admin 或 teacher")
    _ensure_majors_exist(payload.major_ids, session)
    user = User(
        employee_no=employee_no,
        name=name,
        role=payload.role,
        password_hash=hash_password(_initial_password(employee_no, payload.password)),
        is_active=payload.is_active,
        must_change_password=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    _replace_user_major_links(user.id or 0, payload.major_ids, session)
    return _user_read(user, session)


@admin_router.post("/users/batch", response_model=UserBatchResult)
def create_users_batch(
    payload: UserBatchCreate,
    _: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> UserBatchResult:
    """Create teacher accounts from a pasted roster; the initial password is the employee number.

    Duplicates inside the roster and numbers that already have an account are
    skipped rather than failing the whole batch, so the department list can be
    pasted as-is and pasted again later when a few names are added.
    """
    _ensure_majors_exist(payload.major_ids, session)
    created: list[User] = []
    skipped: list[str] = []
    seen: set[str] = set()
    for item in payload.items:
        employee_no = item.employee_no.strip()
        name = item.name.strip()
        if not employee_no or not name:
            raise HTTPException(status_code=400, detail="名单里有一行缺少工号或姓名，请检查后重新提交")
        if employee_no in seen or _find_by_employee_no(employee_no, session) is not None:
            skipped.append(employee_no)
            continue
        seen.add(employee_no)
        user = User(
            employee_no=employee_no,
            name=name,
            role="teacher",
            password_hash=hash_password(employee_no),
            is_active=True,
            must_change_password=True,
        )
        session.add(user)
        created.append(user)
    session.commit()
    for user in created:
        session.refresh(user)
        for major_id in payload.major_ids:
            session.add(UserMajorLink(user_id=user.id or 0, major_id=major_id))
    session.commit()
    return UserBatchResult(created=[_user_read(user, session) for user in created], skipped=skipped)


@admin_router.get("/users", response_model=list[UserRead])
def list_users(
    _: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> list[UserRead]:
    users = session.exec(select(User).order_by(User.employee_no)).all()
    return [_user_read(user, session) for user in users]


@admin_router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    current_admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> UserRead:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="姓名不能为空")
        user.name = name
    if payload.is_active is not None:
        # Deactivating yourself would end the very session that could undo it.
        if not payload.is_active and user.id == current_admin.id:
            raise HTTPException(status_code=400, detail="不能停用当前登录的管理员账号")
        user.is_active = payload.is_active
    session.add(user)
    session.commit()
    if payload.major_ids is not None:
        _replace_user_major_links(user.id or 0, payload.major_ids, session)
    session.refresh(user)
    return _user_read(user, session)


@admin_router.post("/users/{user_id}/password", response_model=StatusResponse)
def reset_user_password(
    user_id: int,
    payload: PasswordReset,
    _: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> StatusResponse:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    user.password_hash = hash_password(_initial_password(user.employee_no, payload.password))
    user.must_change_password = True
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


def _initial_password(employee_no: str, chosen: str) -> str:
    """The password an admin hands out: their choice, or the employee number.

    The employee number is something every teacher already knows and differs
    per person, which beats one shared default the whole department types in.
    Either way the account is flagged to change it on first login.
    """
    chosen = chosen.strip()
    if not chosen:
        return employee_no
    if len(chosen) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"指定的密码至少需要 {MIN_PASSWORD_LENGTH} 位，留空则使用工号作为初始密码",
        )
    return chosen


def _find_by_employee_no(employee_no: str, session: Session) -> User | None:
    return session.exec(select(User).where(User.employee_no == employee_no)).first()


def _ensure_majors_exist(major_ids: list[int], session: Session) -> None:
    for major_id in major_ids:
        if session.get(Major, major_id) is None:
            raise HTTPException(status_code=400, detail=f"专业 {major_id} 不存在，请刷新页面后重试")


def _replace_user_major_links(user_id: int, major_ids: list[int], session: Session) -> None:
    _ensure_majors_exist(major_ids, session)
    existing = session.exec(select(UserMajorLink).where(UserMajorLink.user_id == user_id)).all()
    for link in existing:
        session.delete(link)
    for major_id in major_ids:
        session.add(UserMajorLink(user_id=user_id, major_id=major_id))
    session.commit()


def _user_read(user: User, session: Session) -> UserRead:
    return UserRead(
        id=user.id or 0,
        employee_no=user.employee_no,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        major_ids=user_major_ids(user, session),
    )
