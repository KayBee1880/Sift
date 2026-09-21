from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_requires_no_auth_and_returns_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metrics_endpoint_returns_a_json_counter_snapshot():
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)
