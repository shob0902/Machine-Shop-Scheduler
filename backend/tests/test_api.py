import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", str(tmp_path / "test_shop.db"))
    import importlib
    import config
    importlib.reload(config)
    import db
    importlib.reload(db)
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["success"] is True


def test_generate_schedule(client):
    r = client.post("/api/schedule/generate", json={"strategy": "cheapest", "time_limit_seconds": 8})
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert len(body["data"]["operations"]) > 0


def test_invalid_strategy_returns_400(client):
    r = client.get("/api/schedule?strategy=not_a_real_strategy")
    assert r.status_code == 400
    assert r.get_json()["success"] is False


def test_orders_and_machines_endpoints(client):
    client.post("/api/schedule/generate", json={"strategy": "cheapest", "time_limit_seconds": 8})
    r = client.get("/api/orders")
    assert r.status_code == 200
    assert len(r.get_json()["data"]) >= 20

    r = client.get("/api/machines")
    assert r.status_code == 200
    assert len(r.get_json()["data"]) == 14


def test_disruption_breakdown_endpoint(client):
    client.post("/api/schedule/generate", json={"strategy": "cheapest", "time_limit_seconds": 8})
    r = client.post("/api/disruptions/breakdown", json={
        "machine_id": "GRIND-01", "start_time": "2026-08-25T11:00:00",
        "duration_minutes": 480, "reason": "test", "time_limit_seconds": 8,
    })
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert "comparison" in body["data"]
    assert "owner_action" in body["data"]


def test_disruption_missing_field_returns_400(client):
    r = client.post("/api/disruptions/breakdown", json={"machine_id": "GRIND-01"})
    assert r.status_code == 400
    assert r.get_json()["success"] is False


def test_unknown_route_returns_404(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
