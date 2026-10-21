import logging
from typing import Any, Optional, List, Dict
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("skillmatch.exceptions")

# Traductor y formateador semántico de mensajes de validación Pydantic
SPANISH_VALIDATION_MESSAGES: Dict[str, str] = {
    "missing": "es obligatorio",
    "string_too_short": "es demasiado corto",
    "string_too_long": "es demasiado largo",
    "value_error": "tiene un valor inválido",
    "int_parsing": "debe ser un número entero válido",
    "bool_parsing": "debe ser un valor booleano",
    "enum": "no corresponde a un valor permitido",
}

FIELD_NAME_TRANSLATIONS: Dict[str, str] = {
    "email": "Correo electrónico",
    "password": "Contraseña",
    "remember_me": "Recordar sesión",
    "full_name": "Nombre completo",
    "role": "Rol de usuario",
    "phone_number": "Número de teléfono",
}

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
    Captura errores de validación 422 de Pydantic y los formatea con mensajes profesionales,
    claros y orientados a la experiencia del usuario final.
    """
    errors = exc.errors()
    formatted_errors: List[Dict[str, Any]] = []
    summary_parts: List[str] = []

    for err in errors:
        loc = err.get("loc", [])
        field_raw = str(loc[-1]) if loc else "campo"
        field_label = FIELD_NAME_TRANSLATIONS.get(field_raw, field_raw)

        err_type = err.get("type", "")
        # Determinar mensaje profesional en español
        if "missing" in err_type:
            msg_spanish = f"El campo '{field_label}' es obligatorio."
        elif "email" in err_type or "value_error" in err_type and "email" in field_raw:
            msg_spanish = f"El campo '{field_label}' debe ser una dirección de correo válida."
        elif "too_short" in err_type:
            min_len = err.get("ctx", {}).get("min_length", "")
            msg_spanish = f"El campo '{field_label}' debe tener al menos {min_len} caracteres." if min_len else f"El campo '{field_label}' es demasiado corto."
        else:
            raw_msg = err.get("msg", "Dato inválido")
            msg_spanish = f"Error en '{field_label}': {raw_msg}"

        summary_parts.append(msg_spanish)
        formatted_errors.append({
            "field": field_raw,
            "field_label": field_label,
            "message": msg_spanish,
            "type": err_type,
        })

    # Mensaje principal unificado para UI / Toasts
    if len(summary_parts) == 1:
        summary_message = f"Error de validación: {summary_parts[0]}"
    else:
        summary_message = "Error de validación en los datos enviados: " + "; ".join(summary_parts[:3])
        if len(summary_parts) > 3:
            summary_message += f" (+{len(summary_parts) - 3} errores adicionales)"

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "statuscode": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "message": summary_message,
            "data": {
                "errors": errors,
                "validation_errors": formatted_errors,
            },
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
