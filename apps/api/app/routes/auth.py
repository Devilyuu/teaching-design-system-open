from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import create_access_token, get_current_user, hash_password, user_major_ids, verify_password
from app.db import get_session
from app.models import User
from app.schemas import LoginRequest, PasswordChange, StatusResponse, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

MIN_PASSWORD_LENGTH = 8


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    user = session.exec(select(User).where(User.employee_no == payload.employee_no)).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="工号或密码不正确")
    return TokenResponse(access_token=create_access_token(user))


@router.get("/me", response_model=UserRead)
def read_current_user(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserRead:
    return UserRead(
        id=current_user.id or 0,
        employee_no=current_user.employee_no,
        name=current_user.name,
        role=current_user.role,
        is_active=current_user.is_active,
        must_change_password=current_user.must_change_password,
        major_ids=user_major_ids(current_user, session),
    )


@router.post("/change-password", response_model=StatusResponse)
def change_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> StatusResponse:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    if len(payload.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"新密码至少需要 {MIN_PASSWORD_LENGTH} 位")
    # The employee number is the initial password the admin hands out;
    # "changing" to it would leave the account exactly as exposed as before.
    if payload.new_password == current_user.employee_no:
        raise HTTPException(status_code=400, detail="新密码不能与工号相同")
    current_user.password_hash = hash_password(payload.new_password)
    current_user.must_change_password = False
    session.add(current_user)
    session.commit()
    return StatusResponse(status="ok")
