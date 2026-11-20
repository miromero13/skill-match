"""S1: the browser supervision trial must be unreachable in production."""
import pytest
from fastapi import FastAPI

from app.core.config import Settings, settings
from app.main import app, register_browser_supervision_router

ROUTE = "/api/browser-supervision/trials"


def build(environment: str, flag: bool | None) -> Settings:
    return Settings.model_construct(ENVIRONMENT=environment, BROWSER_SUPERVISION_TRIAL_ENABLED=flag)


def paths(target: FastAPI) -> set[str]:
    return set(target.openapi()["paths"])


@pytest.mark.parametrize(
    ("environment", "flag", "expected"),
    [
        ("production", True, False),
        ("production", None, False),
        ("production", False, False),
        ("development", None, True),
        ("test", None, True),
        ("testing", None, True),
        ("staging", None, False),
        ("staging", True, True),
        ("development", False, False),
    ],
)
def test_trial_flag_truth_table(environment: str, flag: bool | None, expected: bool) -> None:
    assert build(environment, flag).browser_supervision_trial_enabled is expected


def test_router_is_not_registered_when_disabled() -> None:
    target = FastAPI()
    register_browser_supervision_router(target, build("production", True))
    assert ROUTE not in paths(target)


def test_router_is_registered_when_enabled() -> None:
    target = FastAPI()
    register_browser_supervision_router(target, build("development", None))
    assert ROUTE in paths(target)


def test_application_keeps_trial_routes_in_development() -> None:
    assert settings.ENVIRONMENT == "development"
    assert ROUTE in paths(app)
