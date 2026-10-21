from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .services.job_store import JobStore
from .settings import allowed_origins, clerk_issuer

ROLES = frozenset({"doctor", "admin"})

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    user_id: str  # Clerk user ID (the token "sub")
    role: str


@lru_cache(maxsize=4)
def _jwks_client(issuer: str) -> jwt.PyJWKClient:
    # Caches the signing keys; a new key ID (key rotation) triggers one refetch
    return jwt.PyJWKClient(f"{issuer}/.well-known/jwks.json", lifespan=3600)


def _unauthorized(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": code, "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


# A sync dependency: FastAPI runs it in a thread, so a JWKS fetch does not block the event loop
def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """Verify the Clerk session token from the Authorization header."""
    if credentials is None:
        raise _unauthorized("MISSING_TOKEN", "Missing bearer token")

    issuer = clerk_issuer()
    token = credentials.credentials
    try:
        signing_key = _jwks_client(issuer).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"require": ["exp", "iat", "iss", "sub"]},
            leeway=5,
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("TOKEN_EXPIRED", "Token has expired") from None
    except (jwt.InvalidTokenError, jwt.PyJWKClientError):
        raise _unauthorized("INVALID_TOKEN", "Invalid token") from None

    # azp is the origin that requested the token; it must be one of our frontends
    azp = claims.get("azp")
    if azp and azp not in allowed_origins():
        raise _unauthorized("INVALID_TOKEN", "Invalid token")

    # The role comes from Clerk public metadata, which only the server or an admin can change
    role = claims.get("role")
    if role not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "NO_ROLE", "message": "The account has no access role"},
        )
    return CurrentUser(user_id=claims["sub"], role=role)


def get_job_store(request: Request) -> JobStore:
    return request.app.state.job_store
