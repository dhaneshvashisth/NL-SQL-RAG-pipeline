
from enum import Enum
from dataclasses import dataclass


class UserRole(str, Enum):

    ADMIN      = "admin"
    SUPERVISOR = "supervisor"
    AGENT      = "agent"


@dataclass
class TokenData:
    
    user_id:  int
    username: str
    role:     UserRole
    parent_id: int | None = None


@dataclass  
class RBACScope:
   
    filter_column: str | None
   
    filter_value:  int | None
   
    description:   str


def get_rbac_scope(token_data: TokenData) -> RBACScope:

    if token_data.role == UserRole.ADMIN:
        return RBACScope(
            filter_column=None,
            filter_value=None,
            description="Admin: full access to all data"
        )

    elif token_data.role == UserRole.SUPERVISOR:
       
        return RBACScope(
            filter_column="supervisor", 
            filter_value=token_data.user_id,
            description=f"Supervisor {token_data.username}: agents under id={token_data.user_id}"
        )

    elif token_data.role == UserRole.AGENT:
        return RBACScope(
            filter_column="agent_id",
            filter_value=token_data.user_id,
            description=f"Agent {token_data.username}: own transactions only id={token_data.user_id}"
        )

    else:
        raise ValueError(f"Unknown role: {token_data.role}")