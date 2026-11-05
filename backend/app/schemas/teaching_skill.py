from email.policy import default
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

#no se aceptan user_id ni status desde el formulario 

class DeclaredLevel(str, Enum): 
    BEGINNER =  "BEGINNER"
    INTERMEDIATE ="INTERMEDIATE"
    ADVANCED = "ADVANCED"
    EXPERT = "EXPERT"

class TeachingSkillWrite(BaseModel): 
    model_config = ConfigDict(extra = "forbid")

    skill_id :  UUID 
    declared_level : DeclaredLevel
    years_of_experence: int = Field(strict=True, ge=0, le=60)
    description : str | None = Field (default = None , max_length = 2000)
    accepts_points :bool = False
    hourly_points_rate : int | None = Field(default = None , strict= True , le = 2_147_483_647)

    @model_validator(mode  ="after")
    def validate_rare(self)-> "TeachingSkillWrite": 
        if self.accepts_points and self.hourly_points_rate is None : 
            raise ValueError("Debes indicar la tarifa en puntos por hora.")
        
        if not self.accepts_points and self.hourly_points_rate is not None :
            raise ValueError("Desactiva la tarifa si no ofreces clases por puntos")    
        return self
    
class TeachingSkillResponse (BaseModel): 
    id : UUID
    skill_id : UUID
    skill_name : str 
    declared_level: DeclaredLevel
    years_of_experence :  int 
    description :str | None 
    accepts_points: bool 
    hourly_points_rate : int | None 
    status :str 

class AvailableSkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes = True)

    id : UUID
    name : str

