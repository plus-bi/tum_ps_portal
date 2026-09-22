from dataclasses import dataclass
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from .config import settings

bearer = HTTPBearer(auto_error=False)

@dataclass(frozen=True)
class User:
    id: str
    admin: bool = False

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> User:
    cfg = settings()
    if not credentials or not cfg.clerk_jwks_url:
        raise HTTPException(401, "Authentication required")
    try:
        key = jwt.PyJWKClient(cfg.clerk_jwks_url).get_signing_key_from_jwt(credentials.credentials).key
        claims = jwt.decode(credentials.credentials, key, algorithms=["RS256"], issuer=cfg.clerk_issuer, options={"verify_aud": False})
    except Exception as error:
        raise HTTPException(401, "Invalid session") from error
    metadata = claims.get("public_metadata", {})
    return User(str(claims["sub"]), metadata.get("role") == "admin")

def admin_user(user: User = Depends(current_user)) -> User:
    if not user.admin: raise HTTPException(403, "Admin role required")
    return user
