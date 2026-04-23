
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from app.utils.config import config
from app.utils.logger import get_logger
from app.auth.models import TokenData, UserRole

logger = get_logger(__name__)


def create_access_token(user_id : int, username : str, role : str, parent_id : int | None = None) -> str:

    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=config.JWT_EXPIRY_MINUTES)

    payload = {
        "user_id":   user_id,
        "username":  username,
        "role":      role,
        "parent_id": parent_id,
        "exp":       expire,
        "iat":       now,
    }

    token = jwt.encode( payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM )

    logger.info(
        "JWT created | user=%s | role=%s | expires=%s",
        username, role, expire.strftime("%Y-%m-%d %H:%M:%S UTC")
    )
    return token


def decode_access_token(token: str) -> TokenData:

    try:
        payload = jwt.decode( token,  config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM] )

        user_id   = payload.get("user_id")
        username  = payload.get("username")
        role      = payload.get("role")
        parent_id = payload.get("parent_id")

        if user_id is None or username is None or role is None:
            raise ValueError("JWT payload missing required fields")

        token_data = TokenData(
            user_id=user_id,
            username=username,
            role=UserRole(role),
            parent_id=parent_id
        )

        logger.info( "JWT decoded | user=%s | role=%s",  username, role  )
        
        return token_data

    except JWTError as e:
        logger.warning("JWT decode failed | error=%s", str(e))
        raise ValueError(f"Invalid or expired token: {str(e)}")