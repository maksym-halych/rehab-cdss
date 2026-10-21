import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

ISSUER = "https://clerk.example.test"
ORIGIN = "http://localhost:3000"
PROTECTED = "/api/v1/config/test-types"

# Windows asyncio needs a loopback socket pair. External hosts stay blocked.
pytestmark = pytest.mark.allow_hosts(["127.0.0.1", "::1"])

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_token(key=_KEY, **overrides):
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "sub": "user_synthetic",
        "azp": ORIGIN,
        "iat": now,
        "nbf": now,
        "exp": now + 60,
        "role": "doctor",
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})


@pytest.fixture
def client(monkeypatch, database_url):
    from api import dependencies
    from api.app import create_app

    monkeypatch.setenv("CLERK_ISSUER", ISSUER)
    # The JWKS endpoint is replaced by the local test key, so no network call is made
    fake_jwks = SimpleNamespace(
        get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=_KEY.public_key())
    )
    monkeypatch.setattr(dependencies, "_jwks_client", lambda _issuer: fake_jwks)
    with TestClient(create_app()) as http:
        yield http


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def error_code(response):
    return response.json()["detail"]["code"]


def test_health_is_public(client):
    assert client.get("/api/v1/health").status_code == 200


def test_valid_token_is_accepted(client):
    assert client.get(PROTECTED, headers=auth(make_token())).status_code == 200


def test_admin_role_is_accepted(client):
    response = client.get(PROTECTED, headers=auth(make_token(role="admin")))
    assert response.status_code == 200


def test_missing_token_is_rejected(client):
    response = client.get(PROTECTED)
    assert response.status_code == 401
    assert error_code(response) == "MISSING_TOKEN"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_demo_json_needs_a_token(client):
    response = client.get("/api/v1/demo/module1-json")
    assert response.status_code == 401


def test_expired_token_is_rejected(client):
    past = int(time.time()) - 600
    token = make_token(iat=past - 60, nbf=past - 60, exp=past)
    response = client.get(PROTECTED, headers=auth(token))
    assert response.status_code == 401
    assert error_code(response) == "TOKEN_EXPIRED"


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(make_token(key=_OTHER_KEY), id="wrong-signature"),
        pytest.param(make_token(iss="https://other.clerk.test"), id="wrong-issuer"),
        pytest.param(make_token(azp="https://evil.example"), id="foreign-origin"),
        pytest.param(make_token(sub=None), id="no-subject"),
        pytest.param("not-a-jwt", id="malformed"),
    ],
)
def test_invalid_token_is_rejected(client, token):
    response = client.get(PROTECTED, headers=auth(token))
    assert response.status_code == 401
    assert error_code(response) == "INVALID_TOKEN"


@pytest.mark.parametrize("role", [None, "", "patient"])
def test_account_without_role_is_forbidden(client, role):
    response = client.get(PROTECTED, headers=auth(make_token(role=role)))
    assert response.status_code == 403
    assert error_code(response) == "NO_ROLE"


def test_api_does_not_start_without_clerk_issuer():
    from api.app import create_app

    with pytest.raises(RuntimeError, match="CLERK_ISSUER"):
        create_app()


def test_api_does_not_start_without_database_url(monkeypatch):
    from api.app import create_app

    monkeypatch.setenv("CLERK_ISSUER", ISSUER)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_app()
