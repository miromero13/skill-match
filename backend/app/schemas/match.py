from uuid import UUID
from pydantic import BaseModel

class MatchResponse(BaseModel) :
    id: UUID
    counterpart_name : str 
    status : str 
    you_teach: list[str]
    they_teach : list[str]
    
