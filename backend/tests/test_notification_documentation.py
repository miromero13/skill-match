import warnings

from httpx import ASGITransport, AsyncClient
import pytest

from app.main import create_application
from test_notifications import LIST, OPERATIONS, assert_error, inbox  # noqa: F401

pytestmark = pytest.mark.hu25


async def test_swagger_and_openapi_serve_canonical_notification_operations_once():
    app = create_application()
    # FastAPI can keep included routers lazy; direct app.routes traversal does
    # not necessarily expose flattened APIRoutes. Check the generated contract
    # and FastAPI's duplicate-operation warnings instead.
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        app.openapi()
    assert not any("Duplicate Operation ID" in str(item.message) for item in captured)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        docs = await client.get("/docs")
        assert docs.status_code == 200 and "swagger-ui" in docs.text
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json()["paths"]
        for path, method in OPERATIONS:
            operation = paths[path][method]
            assert operation["description"]
            validation = operation["responses"]["422"]["content"]["application/json"]["schema"]
            assert "HTTPValidationError" not in validation.get("$ref", "")
            assert "authorization" in [p["name"] for p in operation["parameters"]]
        assert "post" not in paths[LIST]
        assert len({paths[path][method]["operationId"] for path, method in OPERATIONS}) == len(OPERATIONS)


@pytest.mark.parametrize("params", [{"user_id": "other-user"}, {"sort": "untrusted-sql"}])
async def test_query_rejects_unapproved_filters_without_echoing_input(inbox, params):
    response = await inbox.client.get(LIST, headers=inbox.headers[0], params=params)
    assert_error(response, 422)
    for value in params.values():
        assert value not in response.json()["message"]
