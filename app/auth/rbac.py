
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.auth.jwt_handler import decode_access_token
from app.auth.models import TokenData
from app.utils.logger import get_logger

logger = get_logger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user( token: str = Depends(oauth2_scheme)) -> TokenData:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token_data = decode_access_token(token)
        return token_data
    except ValueError as e:
        logger.warning("Auth failed | error=%s", str(e))
        raise credentials_exception


async def require_admin( token_data: TokenData = Depends(get_current_user)) -> TokenData:

    if token_data.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return token_data


async def require_supervisor_or_above( token_data: TokenData = Depends(get_current_user)) -> TokenData:
    if token_data.role.value == "agent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisor or Admin access required"
        )
    return token_data