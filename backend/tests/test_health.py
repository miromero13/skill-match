import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_check_endpoint(client: AsyncClient):
    """
    Verifica que el endpoint /api/health responda con status 200 y el sobre unificado APIResponse.
    """
    response = await client.get("/api/health")
    assert response.status_code == 200
    
    payload = response.json()
    # Verificación del sobre estándar canónico
    assert "statuscode" in payload
    assert "message" in payload
    assert "data" in payload
    assert payload["statuscode"] == 200
    assert payload["message"] == "Sistema operativo y base de datos conectada exitosamente"
    
    data = payload["data"]
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["version"] == "0.1.0"
    assert "services" in data
