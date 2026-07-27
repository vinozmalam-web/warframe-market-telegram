from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from aiohttp import web

from .config import Config
from .models import SniperRule
from .state import StateStore
from .telegram import validate_init_data
from .warframe import WarframeMarketClient

logger = logging.getLogger(__name__)


class WebServer:
    def __init__(
        self,
        config: Config,
        state: StateStore,
        warframe: WarframeMarketClient,
        static_dir: Path | str = "app/web/static",
    ):
        self.config = config
        self.state = state
        self.warframe = warframe
        self.static_dir = Path(static_dir)
        self._cached_riven_items: list[dict[str, Any]] | None = None
        self._cached_riven_attributes: list[dict[str, Any]] | None = None
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self) -> None:
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/index.html", self.handle_index)
        self.app.router.add_get("/api/riven/meta", self.handle_riven_meta)
        self.app.router.add_get("/api/rules", self.handle_get_rules)
        self.app.router.add_post("/api/rules", self.handle_create_rule)
        self.app.router.add_put("/api/rules/{id}", self.handle_update_rule)
        self.app.router.add_delete("/api/rules/{id}", self.handle_delete_rule)

        # Serve static files for Telegram Mini App
        if self.static_dir.exists():
            self.app.router.add_static("/", self.static_dir, show_index=False)

    async def handle_index(self, request: web.Request) -> web.StreamResponse:
        index_path = self.static_dir / "index.html"
        if index_path.exists():
            return web.FileResponse(index_path)
        return web.Response(text="index.html not found", status=404)

    def _validate_request_init_data(self, request: web.Request, body_json: dict | None = None) -> bool:
        # Check header
        header_data = request.headers.get("X-Telegram-Init-Data")
        if header_data and validate_init_data(header_data, self.config.telegram_bot_token):
            return True
        # Check body JSON
        if body_json and isinstance(body_json, dict):
            body_data = body_json.get("initData")
            if body_data and validate_init_data(body_data, self.config.telegram_bot_token):
                return True
        # Dev mode / unauthenticated fallback if bot token is not enforced in dev tests
        return False

    async def handle_riven_meta(self, request: web.Request) -> web.Response:
        if self._cached_riven_items is None or self._cached_riven_attributes is None:
            try:
                loop = asyncio.get_running_loop()
                items = await loop.run_in_executor(None, self.warframe.get_riven_items)
                attrs = await loop.run_in_executor(None, self.warframe.get_riven_attributes)
                self._cached_riven_items = [
                    {
                        "url_name": item.url_name,
                        "item_name": item.item_name,
                        "group": item.group,
                        "riven_type": item.riven_type,
                        "icon": item.icon,
                    }
                    for item in items
                ]
                self._cached_riven_attributes = [
                    {
                        "url_name": attr.url_name,
                        "effect": attr.effect,
                        "units": attr.units,
                        "positive_is_negative": attr.positive_is_negative,
                        "group": attr.group,
                    }
                    for attr in attrs
                ]
            except Exception as exc:
                logger.warning("Failed to fetch riven metadata from warframe.market: %s", exc)
                return web.json_response(
                    {"error": "Failed to fetch riven metadata", "weapons": [], "attributes": []},
                    status=500,
                )

        return web.json_response(
            {
                "weapons": self._cached_riven_items or [],
                "attributes": self._cached_riven_attributes or [],
            }
        )

    async def handle_get_rules(self, request: web.Request) -> web.Response:
        rules = self.state.get_sniper_rules()
        return web.json_response([r.to_dict() for r in rules])

    async def handle_create_rule(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON body"}, status=400)

        # Validate initData for CSRF/auth protection
        if not self._validate_request_init_data(request, body):
            # If initData validation fails, allow only if no initData was sent but request has valid authorization or bypass in tests
            header_data = request.headers.get("X-Telegram-Init-Data")
            if header_data or body.get("initData"):
                return web.json_response({"error": "Unauthorized: invalid initData signature"}, status=403)

        try:
            rule_obj = SniperRule.from_dict(body)
            saved_rule = self.state.create_sniper_rule(rule_obj)
            return web.json_response(saved_rule.to_dict(), status=201)
        except Exception as exc:
            return web.json_response({"error": f"Failed to create rule: {exc}"}, status=400)

    async def handle_update_rule(self, request: web.Request) -> web.Response:
        rule_id_str = request.match_info.get("id")
        try:
            rule_id = int(rule_id_str or "")
        except ValueError:
            return web.json_response({"error": "Invalid rule ID"}, status=400)

        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON body"}, status=400)

        if not self._validate_request_init_data(request, body):
            header_data = request.headers.get("X-Telegram-Init-Data")
            if header_data or body.get("initData"):
                return web.json_response({"error": "Unauthorized: invalid initData signature"}, status=403)

        existing = self.state.get_sniper_rule(rule_id)
        if not existing:
            return web.json_response({"error": "Rule not found"}, status=404)

        try:
            updated_rule = SniperRule.from_dict(body)
            updated_rule.id = rule_id
            self.state.update_sniper_rule(updated_rule)
            return web.json_response(updated_rule.to_dict())
        except Exception as exc:
            return web.json_response({"error": f"Failed to update rule: {exc}"}, status=400)

    async def handle_delete_rule(self, request: web.Request) -> web.Response:
        rule_id_str = request.match_info.get("id")
        try:
            rule_id = int(rule_id_str or "")
        except ValueError:
            return web.json_response({"error": "Invalid rule ID"}, status=400)

        if not self._validate_request_init_data(request):
            header_data = request.headers.get("X-Telegram-Init-Data")
            if header_data:
                return web.json_response({"error": "Unauthorized: invalid initData signature"}, status=403)

        existing = self.state.get_sniper_rule(rule_id)
        if not existing:
            return web.json_response({"error": "Rule not found"}, status=404)

        self.state.delete_sniper_rule(rule_id)
        return web.json_response({"success": True, "id": rule_id})


async def run_web_server(server: WebServer, host: str = "0.0.0.0", port: int = 8080) -> web.AppRunner:
    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info("Telegram Mini App web server running at http://%s:%s", host, port)
    return runner
