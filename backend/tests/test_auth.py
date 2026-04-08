import os
from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt


@pytest.mark.asyncio
async def test_register_success(client, test_env):
    response = await client.post(
        "/api/auth/register",
        json={"username": "testuser", "password": "Test123!@#"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_username(client, test_env):
    await client.post(
        "/api/auth/register",
        json={"username": "dupeuser", "password": "Test123!@#"},
    )
    response = await client.post(
        "/api/auth/register",
        json={"username": "dupeuser", "password": "Test123!@#"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_register_weak_password(client, test_env):
    response = await client.post(
        "/api/auth/register",
        json={"username": "weakuser", "password": "weakpass"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client, test_env):
    await client.post(
        "/api/auth/register",
        json={"username": "loginuser", "password": "Test123!@#"},
    )
    response = await client.post(
        "/api/auth/login",
        json={"username": "loginuser", "password": "Test123!@#"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_invalid_credentials(client, test_env):
    response = await client.post(
        "/api/auth/login",
        json={"username": "missinguser", "password": "Test123!@#"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_access_protected_endpoint(client, test_env):
    await client.post(
        "/api/auth/register",
        json={"username": "meuser", "password": "Test123!@#"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "meuser", "password": "Test123!@#"},
    )
    token = login.json()["access_token"]
    response = await client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "meuser"


@pytest.mark.asyncio
async def test_access_protected_invalid_token(client, test_env):
    response = await client.get(
        "/api/users/me",
        headers={"Authorization": "Bearer invalid_token"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


@pytest.mark.asyncio
async def test_refresh_token(client, test_env):
    await client.post(
        "/api/auth/register",
        json={"username": "refreshuser", "password": "Test123!@#"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "refreshuser", "password": "Test123!@#"},
    )
    refresh_token = login.json()["refresh_token"]
    response = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client, test_env):
    await client.post(
        "/api/auth/register",
        json={"username": "logoutuser", "password": "Test123!@#"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "logoutuser", "password": "Test123!@#"},
    )
    refresh_token = login.json()["refresh_token"]
    logout = await client.post(
        "/api/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout.status_code == 204
    response = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_rejected(client, test_env):
    secret = os.environ["JWT_SECRET"]
    now = datetime.now(UTC)
    expired = now - timedelta(seconds=60)
    token = jwt.encode(
        {
            "sub": "1",
            "type": "access",
            "iat": int((now - timedelta(seconds=120)).timestamp()),
            "exp": int(expired.timestamp()),
            "jti": "expired",
        },
        secret,
        algorithm="HS256",
    )
    response = await client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
