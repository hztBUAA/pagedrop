from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.actor import Actor, get_actor
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.ratelimit import rate_limit
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RequestCodeRequest,
    ResetPasswordRequest,
    UserOut,
    WhoamiOut,
)
from app.services import auth_service, email_service, verification_service

router = APIRouter(prefix="/auth", tags=["auth"])

_VALID_PURPOSES = {"register", "reset"}


def _set_session_cookie(response: Response, user: User) -> None:
    token = create_access_token(str(user.id))
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


@router.post(
    "/request-code",
    dependencies=[rate_limit("request_code", limit=3, window_seconds=60)],
)
def request_code(payload: RequestCodeRequest, db: Session = Depends(get_db)):
    purpose = payload.purpose
    if purpose not in _VALID_PURPOSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_purpose")

    email = payload.email.lower()
    exists = auth_service.get_user_by_email(db, email) is not None

    if purpose == "register" and exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email_already_registered"
        )

    # For reset on a non-existent account: pretend success (don't leak existence).
    if purpose == "reset" and not exists:
        return {"status": "sent"}

    if verification_service.in_cooldown(db, email, purpose):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="rate_limited")

    code = verification_service.issue_code(db, email, purpose)
    if not email_service.send_verification_code(email, code, purpose):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="email_send_failed"
        )
    return {"status": "sent"}


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[rate_limit("register", limit=5, window_seconds=60)],
)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    if not verification_service.verify_code(db, payload.email, payload.code, "register"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_code")
    try:
        user = auth_service.register_user(db, payload.email, payload.password, payload.name)
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    _set_session_cookie(response, user)
    return user


@router.post(
    "/reset-password",
    response_model=UserOut,
    dependencies=[rate_limit("reset", limit=5, window_seconds=60)],
)
def reset_password(
    payload: ResetPasswordRequest, response: Response, db: Session = Depends(get_db)
):
    if not verification_service.verify_code(db, payload.email, payload.code, "reset"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_code")
    try:
        user = auth_service.set_password(db, payload.email, payload.new_password)
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _set_session_cookie(response, user)
    return user


@router.post(
    "/login",
    response_model=UserOut,
    dependencies=[rate_limit("login", limit=10, window_seconds=60)],
)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    try:
        user = auth_service.authenticate(db, payload.email, payload.password)
    except auth_service.AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials"
        ) from exc
    _set_session_cookie(response, user)
    return user


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(settings.auth_cookie_name, path="/")
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/whoami", response_model=WhoamiOut)
def whoami(actor: Actor = Depends(get_actor)):
    return WhoamiOut(
        type="token" if actor.token else "user",
        user_id=actor.user_id,
        email=actor.user.email if actor.user else None,
        token_id=actor.token_id,
        token_name=actor.token.name if actor.token else None,
        workspace_id=actor.token.workspace_id if actor.token else None,
        scopes=sorted(actor.scopes),
    )
