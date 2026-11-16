from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError
import pytest

from test_notifications import DEFAULTS

pytestmark = pytest.mark.hu25


def emission(**changes):
    return {"user_id": uuid4(), "event_id": uuid4(), "notification_type": "MATCH_RECEIVED",
            "title": " Title ", "message": " Message ", **changes}


@pytest.mark.parametrize("changes", [
    {"title": " "}, {"message": "\n\t"}, {"title": 7}, {"message": False},
    {"title": "x" * 151}, {"message": "x" * 2001}, {"notification_type": "INVALID"},
    {"user_id": "invalid"}, {"event_id": "invalid"}, {"read_at": None}, {"category": "POINTS"},
])
def test_emission_rejects_invalid_or_server_fields(changes):
    from app.schemas.notification import NotificationEmission
    with pytest.raises(ValidationError):
        NotificationEmission(**emission(**changes))


@pytest.mark.parametrize("kind", ["MATCH_RECEIVED", "MATCH_CONFIRMED", "SESSION_PROPOSED", "POINTS_RECEIVED", "OTHER"])
def test_emission_normalizes_valid_text_and_accepts_known_types(kind):
    from app.schemas.notification import NotificationEmission
    item = NotificationEmission(**emission(notification_type=kind))
    assert item.title == "Title" and item.message == "Message"
    maximum = NotificationEmission(**emission(title=" " + "x"*150 + " ", message=" " + "x"*2000 + " "))
    assert len(maximum.title) == 150 and len(maximum.message) == 2000


@pytest.mark.parametrize("scope", ["root", "channels", "categories"])
def test_preferences_forbid_unknown_fields_at_every_level(scope):
    from app.schemas.notification import NotificationPreferencesWrite
    payload = deepcopy(DEFAULTS)
    (payload if scope == "root" else payload[scope])["unknown"] = True
    with pytest.raises(ValidationError):
        NotificationPreferencesWrite.model_validate(payload)


@pytest.mark.parametrize("field", ["revision", "channels", "categories"])
def test_preferences_require_all_sections(field):
    from app.schemas.notification import NotificationPreferencesWrite
    payload = deepcopy(DEFAULTS)
    del payload[field]
    with pytest.raises(ValidationError):
        NotificationPreferencesWrite.model_validate(payload)


@pytest.mark.parametrize("section,field", [
    ("channels", "in_app"), ("channels", "push"), ("channels", "email"),
    ("categories", "INTERCHANGES"), ("categories", "POINTS"), ("categories", "GENERAL"),
])
@pytest.mark.parametrize("invalid", ["false", 0, 1, None])
def test_preferences_booleans_are_strict(section, field, invalid):
    from app.schemas.notification import NotificationPreferencesWrite
    payload = deepcopy(DEFAULTS)
    payload[section][field] = invalid
    with pytest.raises(ValidationError):
        NotificationPreferencesWrite.model_validate(payload)


@pytest.mark.parametrize("revision", [-1, True, "1", 1.5, None])
def test_preference_revision_is_a_nonnegative_strict_integer(revision):
    from app.schemas.notification import NotificationPreferencesWrite
    with pytest.raises(ValidationError):
        NotificationPreferencesWrite.model_validate({**deepcopy(DEFAULTS), "revision": revision})


def test_preferences_roundtrip_defaults_without_shared_mutable_flags():
    from app.schemas.notification import NotificationPreferencesResponse, NotificationPreferencesWrite
    first = NotificationPreferencesResponse.defaults()
    first.channels.push = True
    second = NotificationPreferencesResponse.defaults()
    assert second.model_dump(mode="json") == DEFAULTS
    assert NotificationPreferencesWrite.model_validate(DEFAULTS).model_dump(mode="json") == DEFAULTS


@pytest.mark.parametrize("params", [{"page": 0}, {"page": True}, {"page_size": 101}, {"page_size": 0}, {"category": "INVALID"}, {"unread": "invalid"}, {"user_id": str(uuid4())}])
def test_search_filters_reject_invalid_values(params):
    from app.schemas.notification import NotificationFilters
    with pytest.raises(ValidationError):
        NotificationFilters(**params)


def test_search_filters_accept_http_query_strings():
    from app.schemas.notification import NotificationFilters
    values = NotificationFilters(page="2", page_size="100", unread="false", category="POINTS")
    assert values.page == 2 and values.page_size == 100 and values.unread is False


def test_response_serializes_only_ratified_fields_and_aware_dates():
    from app.models.notification import Notification
    from app.schemas.notification import NotificationResponse
    now = datetime.now(timezone.utc)
    item = Notification(id=uuid4(), user_id=uuid4(), event_id=uuid4(), type="OTHER", title="Title", message="Message", created_at=now)
    result = NotificationResponse.model_validate(item).model_dump(mode="json")
    assert set(result) == {"id", "type", "category", "title", "message", "created_at", "read_at"}
    assert result["category"] == "GENERAL" and result["created_at"].endswith("Z")
    item.created_at = now.replace(tzinfo=None)
    with pytest.raises(ValidationError):
        NotificationResponse.model_validate(item)


def test_response_rejects_logically_deleted_notifications():
    from app.models.notification import Notification
    from app.schemas.notification import NotificationResponse
    now = datetime.now(timezone.utc)
    item = Notification(id=uuid4(), type="OTHER", title="Title", message="Message", created_at=now, deleted_at=now)
    with pytest.raises(ValidationError):
        NotificationResponse.model_validate(item)
