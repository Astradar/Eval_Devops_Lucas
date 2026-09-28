from app import app, r


def test_home_incremente_redis():
    client = app.test_client()
    avant = int(r.get("visites") or 0)
    res = client.get("/")
    assert res.status_code == 200
    assert int(r.get("visites")) == avant + 1


def test_health():
    client = app.test_client()
    res = client.get("/health")
    assert res.status_code == 200
    assert res.data == b"ok"


def test_metrics():
    client = app.test_client()
    client.get("/")
    res = client.get("/metrics")
    assert res.status_code == 200
    assert b"http_requests_total" in res.data
    assert b"http_request_duration_seconds_bucket" in res.data
