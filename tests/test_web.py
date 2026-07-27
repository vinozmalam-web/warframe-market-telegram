from __future__ import annotations

import hmac
import hashlib
from urllib.parse import urlencode

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from market_message.config import Config
from market_message.models import SniperRule
from market_message.state import StateStore
from market_message.telegram import validate_init_data
from market_message.web import WebServer


def generate_test_init_data(bot_token: str) -> str:
    params = {
        "auth_date": "1700000000",
        "query_id": "AAH123",
        "user": '{"id":12345,"first_name":"Tenno"}',
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    params["hash"] = calc_hash
    return urlencode(params)


def test_validate_init_data():
    token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    valid_data = generate_test_init_data(token)
    assert validate_init_data(valid_data, token) is True
    assert validate_init_data("invalid=data&hash=123", token) is False


@pytest.mark.anyio
async def test_web_server_rules_crud(tmp_path):
    config = Config(
        warframe_email="test@example.com",
        warframe_password="pass",
        telegram_bot_token="123456:ABC-DEF",
        telegram_chat_id="123",
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
        # GET empty rules
        resp = await client.get("/api/rules")
        assert resp.status == 200
        data = await resp.json()
        assert data == []

        # POST create rule
        new_rule_data = {
            "name": "Rubico CC",
            "weapon_url_name": "rubico",
            "max_price": 1000,
            "is_active": True,
        }
        resp = await client.post("/api/rules", json=new_rule_data)
        assert resp.status == 201
        created = await resp.json()
        assert created["id"] is not None
        assert created["name"] == "Rubico CC"

        # GET rules again
        resp = await client.get("/api/rules")
        rules = await resp.json()
        assert len(rules) == 1

        # DELETE rule
        rule_id = created["id"]
        resp = await client.delete(f"/api/rules/{rule_id}")
        assert resp.status == 200

        resp = await client.get("/api/rules")
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

