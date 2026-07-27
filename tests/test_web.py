from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlencode

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from market_message.config import Config
from market_message.models import SniperRule
from market_message.state import StateStore
from market_message.telegram import extract_user_from_init_data, validate_init_data
from market_message.web import WebServer


def generate_test_init_data(bot_token: str, user_id: int = 123) -> str:
    params = {
        "auth_date": "1700000000",
        "query_id": "AAH123",
        "user": f'{{"id":{user_id},"first_name":"Tenno"}}',
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    params["hash"] = calc_hash
    return urlencode(params)


def test_validate_init_data():
    token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    valid_data = generate_test_init_data(token, user_id=123)
    assert validate_init_data(valid_data, token) is True
    assert validate_init_data("invalid=data&hash=123", token) is False
    user = extract_user_from_init_data(valid_data, token)
    assert user is not None
    assert user.get("id") == 123


@pytest.mark.anyio
async def test_web_server_auth_and_crud(tmp_path):
    config = Config(
        warframe_email="test@example.com",
        warframe_password="pass",
        telegram_bot_token="123456:ABC-DEF",
        telegram_chat_id="123",
        web_app_secret_token="secret123",
        state_path=tmp_path / "state.sqlite",
    )
    state = StateStore(config.state_path)

    # Mock Warframe client
    class DummyWarframe:
        def get_riven_items(self):
            return []

        def get_riven_attributes(self):
            return []

    web_server = WebServer(config, state, DummyWarframe(), static_dir=tmp_path)
    app = web_server.app

    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. Unauthenticated request should fail (401)
        resp = await client.get("/api/rules")
        assert resp.status == 401

        # 2. Request from wrong Telegram user ID should fail (401)
        wrong_init_data = generate_test_init_data(config.telegram_bot_token, user_id=99999)
        resp = await client.get("/api/rules", headers={"X-Telegram-Init-Data": wrong_init_data})
        assert resp.status == 401

        # 3. Request with valid Telegram initData for matching telegram_chat_id (123) should succeed
        valid_init_data = generate_test_init_data(config.telegram_bot_token, user_id=123)
        auth_headers = {"X-Telegram-Init-Data": valid_init_data}

        resp = await client.get("/api/rules", headers=auth_headers)
        assert resp.status == 200
        data = await resp.json()
        assert data == []

        # 4. POST create rule with valid initData header
        new_rule_data = {
            "name": "Rubico CC",
            "weapon_url_name": "rubico",
            "max_price": 1000,
            "is_active": True,
        }
        resp = await client.post("/api/rules", json=new_rule_data, headers=auth_headers)
        assert resp.status == 201
        created = await resp.json()
        assert created["id"] is not None
        assert created["name"] == "Rubico CC"

        # 5. Access with Secret Token header
        token_headers = {"X-Auth-Token": "secret123"}
        resp = await client.get("/api/rules", headers=token_headers)
        assert resp.status == 200
        rules = await resp.json()
        assert len(rules) == 1

        # 6. DELETE rule with Secret Token header
        rule_id = created["id"]
        resp = await client.delete(f"/api/rules/{rule_id}", headers=token_headers)
        assert resp.status == 200

        resp = await client.get("/api/rules", headers=auth_headers)
        rules = await resp.json()
        assert len(rules) == 0
    finally:
        await client.close()


@pytest.mark.anyio
async def test_web_server_serves_index(tmp_path):
    (tmp_path / "index.html").write_text("<!DOCTYPE html><html><body>Test SPA</body></html>")
    (tmp_path / "app.js").write_text("console.log('test');")

    config = Config(
        warframe_email="test@example.com",
        warframe_password="pass",
        telegram_bot_token="123456:ABC-DEF",
        telegram_chat_id="123",
        state_path=tmp_path / "state.sqlite",
    )
    state = StateStore(config.state_path)

    class DummyWarframe:
        pass

    web_server = WebServer(config, state, DummyWarframe(), static_dir=tmp_path)
    server = TestServer(web_server.app)
    client = TestClient(server)
    await client.start_server()

    try:
        # GET / should return index.html
        resp = await client.get("/")
        assert resp.status == 200
        text = await resp.text()
        assert "Test SPA" in text

        # GET /index.html should return index.html
        resp_idx = await client.get("/index.html")
        assert resp_idx.status == 200
        assert "Test SPA" in await resp_idx.text()

        # GET /app.js should return app.js static file
        resp_js = await client.get("/app.js")
        assert resp_js.status == 200
        assert "console.log" in await resp_js.text()
    finally:
        await client.close()


