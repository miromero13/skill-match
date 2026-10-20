from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel, Field

DataT = TypeVar("DataT")

class APIResponse(BaseModel, Generic[DataT]):
    """
    Contrato canónico de respuesta de la API de SkillMatch.
    Obligatorio en todas las respuestas para garantizar predictibilidad en el cliente.
    """
    statuscode: int = Field(
        ...,
        description="Código de estado HTTP representativo (200, 201, 400, 404, 500, etc.)"
    )
    message: str = Field(
        ...,
        description="Mensaje claro y descriptivo del resultado o del error ocurrido"
    )
    data: Optional[DataT] = Field(
        default=None,
        description="Payload con los datos de respuesta o null si no aplica"
    )
    count: Optional[int] = Field(
        default=None,
        description="Cantidad total de registros devueltos (exclusivo para listados paginados)"
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "statuscode": 200,
                "message": "Operación completada exitosamente",
                "data": {},
                "count": 0
            }
        }
