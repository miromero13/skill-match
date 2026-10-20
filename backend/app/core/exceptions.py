import logging
from typing import Any, Optional
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("skillmatch.exceptions")

class SkillMatchException(Exception):
    """Excepción base para lógica de dominio de SkillMatch."""
    def __init__(self, message: str, statuscode: int = status.HTTP_400_BAD_REQUEST, data: Optional[Any] = None):
        self.message = message
        self.statuscode = statuscode
        self.data = data
        super().__init__(message)


async def skillmatch_exception_handler(request: Request, exc: SkillMatchException) -> JSONResponse:
    """Manejo de excepciones de dominio específicas."""
    return JSONResponse(
        status_code=exc.statuscode,
        content={
            "statuscode": exc.statuscode,
            "message": exc.message,
            "data": exc.data,
            "count": None,
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Captura excepciones HTTP estándar y las formatea bajo el sobre canónico APIResponse.
    """
    message = exc.detail if isinstance(exc.detail, str) else "Ha ocurrido un error en la solicitud"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "statuscode": exc.status_code,
            "message": message,
            "data": None,
            "count": None,
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Captura errores de validación 422 de Pydantic y los formatea limpiamente sin exponer estructuras crudas.
    """
    errors = exc.errors()
    # Construir un mensaje amigable resumiendo el primer o principales campos con error
    field_errors = []
    for err in errors:
        loc = " -> ".join([str(x) for x in err.get("loc", []) if x != "body"])
        msg = err.get("msg", "Dato inválido")
        field_errors.append(f"{loc}: {msg}" if loc else msg)

    summary_message = "Error de validación en los datos enviados: " + "; ".join(field_errors[:3])
    if len(field_errors) > 3:
        summary_message += f" (+{len(field_errors) - 3} errores más)"

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "statuscode": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "message": summary_message,
            "data": {"errors": errors},
            "count": len(errors),
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Captura cualquier excepción 500 no controlada para evitar caídas o filtrado de secretos.
    """
    logger.exception(f"Unhandled Exception en {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "statuscode": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "Error interno del servidor. Por favor intenta nuevamente más tarde.",
            "data": None,
            "count": None,
        },
    )
