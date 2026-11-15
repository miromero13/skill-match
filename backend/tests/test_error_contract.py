import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, field_validator
from starlette.exceptions import HTTPException

from app.core.exceptions import (
    SkillMatchException,
    http_exception_handler,
    skillmatch_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)


class SensitivePayload(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def reject_password(cls, value: str) -> str:
        # A validator can accidentally include submitted data in its exception.
        raise ValueError(f"Rejected secret: {value}")


@pytest.fixture
async def error_client():
    app = FastAPI()
    app.add_exception_handler(SkillMatchException, skillmatch_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    @app.get("/domain")
    async def domain_error():
        raise SkillMatchException("Recurso no encontrado", 404, {"private": "hidden"})

    @app.get("/http")
    async def http_error():
        raise HTTPException(401, "Token requerido", headers={"WWW-Authenticate": "Bearer"})

    @app.get("/unexpected")
    async def unexpected_error():
        raise RuntimeError("internal-diagnostic-only")

    @app.post("/validation")
    async def validation_error(payload: SensitivePayload):
        return payload

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.parametrize(
    ("path", "status_code", "message"),
    [
        ("/domain", 404, "Recurso no encontrado"),
        ("/http", 401, "Token requerido"),
        (
            "/unexpected", 500,
            "Error interno del servidor. Por favor intenta nuevamente más tarde.",
        ),
    ],
)
async def test_errors_have_only_the_confirmed_envelope(error_client, path, status_code, message):
    response = await error_client.get(path)
    assert response.status_code == status_code
    assert response.json() == {"statuscode": status_code, "message": message, "data": None}


async def test_http_error_preserves_protocol_headers(error_client):
    response = await error_client.get("/http")
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_validation_does_not_echo_input_or_validator_exception(error_client):
    response = await error_client.post("/validation", json={"password": "private-test-value"})
    assert response.status_code == 422
    body = response.json()
    assert set(body) == {"statuscode", "message", "data"}
    assert body["data"] is None
    assert "Contraseña" in body["message"]
    assert "private-test-value" not in response.text
    assert "Rejected secret" not in response.text


def test_openapi_documents_the_actual_validation_envelope():
    from app.main import create_application

    spec = create_application().openapi()
    response = spec["paths"]["/api/users/me/teaching-skills"]["post"]["responses"]["422"]
    reference = response["content"]["application/json"]["schema"]["$ref"]
    schema = spec["components"]["schemas"][reference.rsplit("/", 1)[1]]
    assert {"statuscode", "message", "data"} <= schema["properties"].keys()
    assert schema["properties"]["data"]["type"] == "null"
    assert "detail" not in schema["properties"]
