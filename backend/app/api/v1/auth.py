import secrets

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.actor import Actor, get_actor
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.ratelimit import rate_limit
from app.core.security import create_access_token, sign_oauth_state, verify_oauth_state
from app.models.user import User
from app.schemas.auth import (
    GithubAuthRequest,
    LoginRequest,
    OAuthCallbackRequest,
    OAuthProvidersOut,
    OAuthStartOut,
    RegisterRequest,
    RequestCodeRequest,
    ResetPasswordRequest,
    UserOut,
    WhoamiOut,
)
from app.services import (
    auth_service,
    email_service,
    github_oauth_service,
    oauth_providers,
    verification_service,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_VALID_PURPOSES = {"register", "reset"}
_OAUTH_STATE_COOKIE = "pd_oauth_state"


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


@router.post(
    "/github",
    response_model=UserOut,
    dependencies=[rate_limit("github", limit=10, window_seconds=60)],
)
def github_auth(payload: GithubAuthRequest, response: Response, db: Session = Depends(get_db)):
    """CLI device flow: trade a GitHub access token (obtained by the CLI) for a session."""
    try:
        identity = github_oauth_service.fetch_github_identity(payload.access_token)
    except github_oauth_service.GithubOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    user = auth_service.upsert_oauth_user(
        db,
        provider="github",
        provider_account_id=identity.id,
        login=identity.login,
        email=identity.email,
        name=identity.name,
    )
    _set_session_cookie(response, user)
    return user


@router.get("/oauth/providers", response_model=OAuthProvidersOut)
def oauth_providers_list():
    return OAuthProvidersOut(providers=oauth_providers.enabled_providers())


@router.get("/oauth/{provider}/start", response_model=OAuthStartOut)
def oauth_start(provider: str, response: Response):
    if not oauth_providers.is_enabled(provider):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="provider_disabled")

    nonce = secrets.token_urlsafe(24)
    state_payload: dict = {"provider": provider, "nonce": nonce}
    code_challenge = None
    if oauth_providers.uses_pkce(provider):
        verifier, code_challenge = oauth_providers.generate_pkce()
        state_payload["verifier"] = verifier

    signed = sign_oauth_state(state_payload)
    response.set_cookie(
        key=_OAUTH_STATE_COOKIE,
        value=signed,
        max_age=settings.oauth_state_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    authorize_url = oauth_providers.build_authorize_url(
        provider, state=nonce, code_challenge=code_challenge
    )
    return OAuthStartOut(authorize_url=authorize_url)


@router.post(
    "/oauth/callback",
    response_model=UserOut,
    dependencies=[rate_limit("oauth", limit=10, window_seconds=60)],
)
def oauth_callback(
    payload: OAuthCallbackRequest,
    response: Response,
    db: Session = Depends(get_db),
    pd_oauth_state: str | None = Cookie(default=None),
):
    claims = verify_oauth_state(pd_oauth_state) if pd_oauth_state else None
    if not claims or claims.get("nonce") != payload.state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_state")
    provider = claims.get("provider", "")
    try:
        identity = oauth_providers.exchange_and_fetch_identity(
            provider, code=payload.code, code_verifier=claims.get("verifier")
        )
    except oauth_providers.OAuthProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    user = auth_service.upsert_oauth_user(
        db,
        provider=identity.provider,
        provider_account_id=identity.account_id,
        login=identity.login,
        email=identity.email,
        name=identity.name,
    )
    response.delete_cookie(_OAUTH_STATE_COOKIE, path="/")
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
