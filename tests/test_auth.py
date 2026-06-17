import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import require_api_key
from app.config import Settings, get_settings


def make_client():
    app = FastAPI()

    @app.get("/guarded", dependencies=[Depends(require_api_key)])
    def guarded():
        return {"ok": True}

    app.dependency_overrides[get_settings] = lambda: Settings(api_key="secret")
    return TestClient(app)


def test_missing_key_rejected():
    assert make_client().get("/guarded").status_code == 401


def test_wrong_key_rejected():
    assert make_client().get("/guarded", headers={"X-API-Key": "nope"}).status_code == 401


def test_correct_key_allowed():
    r = make_client().get("/guarded", headers={"X-API-Key": "secret"})
    assert r.status_code == 200 and r.json() == {"ok": True}
