from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_catalog_and_reference_endpoints():
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/catalog").status_code == 503
    assert client.get("/api/v1/projects").status_code == 503
    assert len(client.get("/api/v1/chairs").json()) == 61
    assert len(client.get("/api/v1/departments").json()) == 7
    assert client.get("/api/v1/bookmarks").status_code == 401
    assert client.get("/api/v1/admin/source-health").status_code == 401

def test_required_route_surface_is_registered():
    paths = set(app.openapi()["paths"])
    assert {"/api/v1/bookmarks", "/api/v1/saved-searches", "/api/v1/webhooks/clerk",
            "/api/v1/webhooks/resend", "/api/v1/admin/source-health",
            "/api/v1/admin/crawl-history", "/api/v1/admin/reviews"} <= paths
