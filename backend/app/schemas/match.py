from uuid import UUID
from pydantic import BaseModel

class MatchResponse(BaseModel) :
    id: UUID
    counterpart_avatar_url: str | None = None
    member_name: str
    member_avatar_url: str | None = None
    you_verified: list[str]
    they_verified: list[str]
    counterpart_name : str 
    status : str 
    you_teach: list[str]
    they_teach : list[str]
    
