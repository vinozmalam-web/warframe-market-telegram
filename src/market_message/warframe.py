from __future__ import annotations

import json
import logging
import secrets
import threading
import time
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

from .config import Config
from .models import (
    AuctionAttribute,
    AuctionItem,
    ChatSummary,
    IncomingMessage,
    RivenAttribute,
    RivenItem,
)

logger = logging.getLogger(__name__)

FALLBACK_RIVEN_ATTRIBUTES: list[RivenAttribute] = [
    RivenAttribute(url_name="critical_chance", effect="Critical Chance", positive_is_negative=False),
    RivenAttribute(url_name="critical_damage", effect="Critical Damage", positive_is_negative=False),
    RivenAttribute(url_name="base_damage_/_melee_damage", effect="Damage", positive_is_negative=False),
    RivenAttribute(url_name="multishot", effect="Multishot", positive_is_negative=False),
    RivenAttribute(url_name="fire_rate_/_attack_speed", effect="Fire Rate / Attack Speed", positive_is_negative=False),
    RivenAttribute(url_name="toxin_damage", effect="Toxin", positive_is_negative=False),
    RivenAttribute(url_name="heat_damage", effect="Heat", positive_is_negative=False),
    RivenAttribute(url_name="cold_damage", effect="Cold", positive_is_negative=False),
    RivenAttribute(url_name="electric_damage", effect="Electricity", positive_is_negative=False),
    RivenAttribute(url_name="status_chance", effect="Status Chance", positive_is_negative=False),
    RivenAttribute(url_name="status_duration", effect="Status Duration", positive_is_negative=False),
    RivenAttribute(url_name="slash_damage", effect="Slash", positive_is_negative=False),
    RivenAttribute(url_name="puncture_damage", effect="Puncture", positive_is_negative=False),
    RivenAttribute(url_name="impact_damage", effect="Impact", positive_is_negative=False),
    RivenAttribute(url_name="punch_through", effect="Punch Through", positive_is_negative=False),
    RivenAttribute(url_name="reload_speed", effect="Reload Speed", positive_is_negative=False),
    RivenAttribute(url_name="magazine_capacity", effect="Magazine Capacity", positive_is_negative=False),
    RivenAttribute(url_name="ammo_maximum", effect="Ammo Maximum", positive_is_negative=False),
    RivenAttribute(url_name="projectile_speed", effect="Projectile Speed", positive_is_negative=False),
    RivenAttribute(url_name="recoil", effect="Weapon Recoil", positive_is_negative=True),
    RivenAttribute(url_name="range", effect="Range", positive_is_negative=False),
    RivenAttribute(url_name="channeling_damage", effect="Initial Combo", positive_is_negative=False),
    RivenAttribute(url_name="combo_duration", effect="Combo Duration", positive_is_negative=False),
    RivenAttribute(url_name="chance_to_gain_extra_combo_count", effect="Additional Combo Count Chance", positive_is_negative=False),
    RivenAttribute(url_name="chance_to_gain_combo_count", effect="Chance to Gain Combo Count", positive_is_negative=False),
    RivenAttribute(url_name="finisher_damage", effect="Finisher Damage", positive_is_negative=False),
    RivenAttribute(url_name="channeling_efficiency", effect="Heavy Attack Efficiency", positive_is_negative=False),
    RivenAttribute(url_name="damage_vs_grineer", effect="Damage to Grineer", positive_is_negative=False),
    RivenAttribute(url_name="damage_vs_corpus", effect="Damage to Corpus", positive_is_negative=False),
    RivenAttribute(url_name="damage_vs_infested", effect="Damage to Infested", positive_is_negative=False),
    RivenAttribute(url_name="zoom", effect="Zoom", positive_is_negative=True),
    RivenAttribute(url_name="critical_chance_on_slide_attack", effect="Critical Chance for Slide Attack", positive_is_negative=False),
]

WEAPON_RU_NAMES: dict[str, str] = {
    "rubico": "Рубико",
    "torid": "Торид",
    "glaive": "Глефа",
    "burston": "Берстон",
    "latron": "Летрон",
    "lex": "Лекс",
    "strun": "Струн",
    "nataruk": "Натарук",
    "stropha": "Строфа",
    "kronen": "Кронен",
    "kuva_bramma": "Кува Брамма",
    "kuva_zarr": "Кува Зарр",
    "felarx": "Феларкс",
    "phenmor": "Фенмор",
    "laetum": "Лэтум",
    "cerata": "Церата",
    "nikana": "Никана",
    "acceltra": "Акцелтра",
    "ignis": "Игнис",
    "soma": "Сома",
    "vectis": "Вектис",
    "orthos": "Ортос",
    "gram": "Грам",
    "sporahtrix": "Споратрикс",
    "trumna": "Трумна",
    "cedo": "Цедо",
    "epitaph": "Эпитафия",
    "ocucor": "Окукор",
    "synapse": "Синапс",
    "amprex": "Ампрекс",
    "lanka": "Ланка",
    "kuva_nukor": "Кува Нукор",
    "tenet_arca_plasmor": "Тенет Арка Плазмор",
    "tenet_envoy": "Тенет Посланник",
    "corvas": "Корвас",
    "pyana": "Пьяна",
    "bo": "Бо",
    "karyst": "Карист",
    "skana": "Скана",
    "redeemer": "Искупитель",
    "guandao": "Гуаньдао",
    "reaper_prime": "Жнец Прайм",
    "tipedo": "Типедо",
    "cestra": "Цестра",
    "furis": "Фурис",
    "vasto": "Васто",
    "magnus": "Магнус",
    "aklex": "Аклекс",
    "akbolto": "Акболто",
    "boltor": "Болтор",
    "grakata": "Граката",
    "karak": "Карак",
    "gorgon": "Горгон",
    "dera": "Дера",
    "supra": "Супра",
    "cinta": "Синта",
    "dread": "Страх",
    "paris": "Парис",
    "cernos": "Чернос",
    "daikyu": "Дайкю",
    "zarr": "Зарр",
    "tonkor": "Тонкор",
    "ogris": "Огрис",
    "penta": "Пента",
    "opticor": "Оптикор",
    "lenz": "Ленз",
    "tigris": "Тигрис",
    "boar": "Боар",
    "hek": "Хек",
    "sobek": "Собек",
    "kohm": "Хом",
    "exergis": "Экзергис",
    "arca_plasmor": "Арка Плазмор",
    "fulmin": "Фульмин",
    "baza": "База",
    "sybaris": "Сибарис",
    "chakkhurr": "Чаккхур",
    "stalta": "Стальта",
    "quellor": "Квеллор",
    "gotva_prime": "Готва Прайм",
    "bubonico": "Бубонико",
    "kompressa": "Компресса",
    "knell": "Кнелл",
    "pyranha": "Пиранья",
    "cycron": "Цикрон",
    "plinx": "Плинкс",
    "catchmoon": "Ловец Лун",
    "tombfinger": "Гробопалец",
    "rattlegut": "Грохотун",
    "sporelacer": "Спорострел",
    "gaze": "Взгляд",
}

FALLBACK_RIVEN_ITEMS: list[RivenItem] = [
    RivenItem(url_name="rubico", item_name="Rubico", group="primary", riven_type="sniper", ru_name="Рубико"),
    RivenItem(url_name="torid", item_name="Torid", group="primary", riven_type="rifle", ru_name="Торид"),
    RivenItem(url_name="glaive", item_name="Glaive", group="melee", riven_type="melee", ru_name="Глефа"),
    RivenItem(url_name="burston", item_name="Burston", group="primary", riven_type="rifle", ru_name="Берстон"),
    RivenItem(url_name="latron", item_name="Latron", group="primary", riven_type="rifle", ru_name="Летрон"),
    RivenItem(url_name="lex", item_name="Lex", group="secondary", riven_type="pistol", ru_name="Лекс"),
    RivenItem(url_name="strun", item_name="Strun", group="primary", riven_type="shotgun", ru_name="Струн"),
    RivenItem(url_name="nataruk", item_name="Nataruk", group="primary", riven_type="bow", ru_name="Натарук"),
    RivenItem(url_name="stropha", item_name="Stropha", group="melee", riven_type="melee", ru_name="Строфа"),
    RivenItem(url_name="kronen", item_name="Kronen", group="melee", riven_type="melee", ru_name="Кронен"),
    RivenItem(url_name="kuva_bramma", item_name="Kuva Bramma", group="primary", riven_type="bow", ru_name="Кува Брамма"),
    RivenItem(url_name="kuva_zarr", item_name="Kuva Zarr", group="primary", riven_type="shotgun", ru_name="Кува Зарр"),
    RivenItem(url_name="felarx", item_name="Felarx", group="primary", riven_type="shotgun", ru_name="Феларкс"),
    RivenItem(url_name="phenmor", item_name="Phenmor", group="primary", riven_type="rifle", ru_name="Фенмор"),
    RivenItem(url_name="laetum", item_name="Laetum", group="secondary", riven_type="pistol", ru_name="Лэтум"),
    RivenItem(url_name="cerata", item_name="Cerata", group="melee", riven_type="melee", ru_name="Церата"),
    RivenItem(url_name="nikana", item_name="Nikana", group="melee", riven_type="melee", ru_name="Никана"),
]

FALLBACK_LICH_ITEMS: list[RivenItem] = [
    RivenItem(url_name="kuva_zarr", item_name="Kuva Zarr", group="primary", ru_name="Кува Зарр"),
    RivenItem(url_name="kuva_bramma", item_name="Kuva Bramma", group="primary", ru_name="Кува Брамма"),
    RivenItem(url_name="kuva_nukor", item_name="Kuva Nukor", group="secondary", ru_name="Кува Нукор"),
    RivenItem(url_name="kuva_chakkhurr", item_name="Kuva Chakkhurr", group="primary", ru_name="Кува Чаккхур"),
    RivenItem(url_name="kuva_hek", item_name="Kuva Hek", group="primary", ru_name="Кува Хек"),
    RivenItem(url_name="kuva_shildeg", item_name="Kuva Shildeg", group="melee", ru_name="Кува Шилдег"),
    RivenItem(url_name="kuva_tonkor", item_name="Kuva Tonkor", group="primary", ru_name="Кува Тонкор"),
    RivenItem(url_name="kuva_ogris", item_name="Kuva Ogris", group="primary", ru_name="Кува Огрис"),
    RivenItem(url_name="kuva_drakgoon", item_name="Kuva Drakgoon", group="primary", ru_name="Кува Дракгун"),
]

FALLBACK_SISTER_ITEMS: list[RivenItem] = [
    RivenItem(url_name="tenet_arca_plasmor", item_name="Tenet Arca Plasmor", group="primary", ru_name="Тенет Арка Плазмор"),
    RivenItem(url_name="tenet_envoy", item_name="Tenet Envoy", group="primary", ru_name="Тенет Посланник"),
    RivenItem(url_name="tenet_cycron", item_name="Tenet Cycron", group="secondary", ru_name="Тенет Цикрон"),
    RivenItem(url_name="tenet_exec", item_name="Tenet Exec", group="melee", ru_name="Тенет Экзек"),
    RivenItem(url_name="tenet_plinx", item_name="Tenet Plinx", group="secondary", ru_name="Тенет Плинкс"),
    RivenItem(url_name="tenet_diplos", item_name="Tenet Diplos", group="secondary", ru_name="Тенет Диплос"),
    RivenItem(url_name="tenet_spirex", item_name="Tenet Spirex", group="secondary", ru_name="Тенет Спайрекс"),
]


class WarframeMarketError(RuntimeError):
    """Base error for Warframe Market API failures."""


class AuthenticationError(WarframeMarketError):
    """Raised when the stored Warframe Market session is invalid."""


class WarframeMarketClient:
    def __init__(self, config: Config, device_id: str):
        self.config = config
        self.device_id = device_id
        self.current_user_id: str | None = None
        self._csrf_token: str | None = None
        self._rate_limit_lock = threading.Lock()
        self._request_timestamps: list[float] = []
        self._max_rps = getattr(config, "warframe_max_requests_per_second", 3.0)
        self._max_rpm = getattr(config, "warframe_max_requests_per_minute", 10.0)
        self._min_request_interval: float = 1.0 / self._max_rps if self._max_rps > 0 else 0.0
        import httpx

        self._client = httpx.Client(
            follow_redirects=True,
            timeout=config.request_timeout_seconds,
            headers={"User-Agent": "market-message/0.1"},
        )
        if getattr(config, "warframe_jwt_token", ""):
            token = config.warframe_jwt_token
            self._client.cookies.set("JWT", token, domain=".warframe.market")
            self._client.cookies.set("JWT", token, domain="api.warframe.market")
            self._client.cookies.set("JWT", token)
        if getattr(config, "warframe_csrf_token", ""):
            self._csrf_token = config.warframe_csrf_token

    def close(self) -> None:
        self._client.close()

    def login(self) -> None:
        jwt_token = getattr(self.config, "warframe_jwt_token", "")
        if jwt_token:
            token = jwt_token
            self._client.cookies.set("JWT", token, domain=".warframe.market")
            self._client.cookies.set("JWT", token, domain="api.warframe.market")
            self._client.cookies.set("JWT", token)
            try:
                data = self.list_chats()
                self.current_user_id = extract_user_id_from_chats(data) or "session_user"
                logger.info("Successfully authenticated to Warframe Market using WARFRAME_MARKET_JWT_TOKEN (user_id=%s)", self.current_user_id)
                return
            except Exception as exc:
                raise AuthenticationError(
                    f"WARFRAME_MARKET_JWT_TOKEN session validation failed ({exc}). "
                    "Please verify that WARFRAME_MARKET_JWT_TOKEN in your .env file is valid and not expired (copy fresh JWT cookie from browser DevTools)."
                ) from exc

        csrf_token = getattr(self.config, "warframe_csrf_token", "")
        if csrf_token:
            self._csrf_token = csrf_token
        else:
            self._csrf_token = self._fetch_csrf_token()

        if not self.config.warframe_email or not self.config.warframe_password:
            raise AuthenticationError(
                "Missing Warframe Market credentials. Please provide WARFRAME_MARKET_JWT_TOKEN or WARFRAME_MARKET_EMAIL / WARFRAME_MARKET_PASSWORD in your .env file."
            )

        payload = {
            "email": self.config.warframe_email,
            "password": self.config.warframe_password,
            "auth_type": "header",
            "device_id": self.device_id,
        }
        data = self._request("POST", "/auth/signin", json=payload, csrf=True)
        user = _unwrap_payload(data).get("user", {})
        user_id = user.get("id")
        if not user_id:
            raise WarframeMarketError("Warframe Market sign-in response did not include user id")
        self.current_user_id = str(user_id)
        logger.info("Logged in to Warframe Market via official API as user id %s", self.current_user_id)

    def list_chats(self) -> dict[str, Any]:
        return self._request("GET", "/im/chats")

    def get_chat(self, chat_id: str) -> dict[str, Any]:
        return self._request("GET", f"/im/chats/{chat_id}")

    def get_riven_items(self) -> list[RivenItem]:
        try:
            data = self._request("GET", "/v2/riven/weapons")
            items = extract_riven_items(data)
            if items:
                return items
        except Exception as exc:
            logger.warning("Failed to fetch riven weapons from v2 API: %s", exc)

        try:
            data = self._request("GET", "/riven/items")
            items = extract_riven_items(data)
            if items:
                return items
        except Exception as exc:
            logger.warning("Failed to fetch riven items from v1 API: %s", exc)

        logger.info("Using fallback static riven items list")
        return FALLBACK_RIVEN_ITEMS

    def get_lich_weapons(self) -> list[RivenItem]:
        try:
            data = self._request("GET", "/v2/lich/weapons")
            items = extract_riven_items(data)
            if items:
                return items
        except Exception as exc:
            logger.warning("Failed to fetch lich weapons from v2 API: %s", exc)
        return FALLBACK_LICH_ITEMS

    def get_sister_weapons(self) -> list[RivenItem]:
        try:
            data = self._request("GET", "/v2/sister/weapons")
            items = extract_riven_items(data)
            if items:
                return items
        except Exception as exc:
            logger.warning("Failed to fetch sister weapons from v2 API: %s", exc)
        return FALLBACK_SISTER_ITEMS

    def get_items_by_type(self, type_: str = "riven") -> list[RivenItem]:
        if type_ in ("kuva_lich", "lich"):
            return self.get_lich_weapons()
        if type_ in ("sister_of_parvos", "sister"):
            return self.get_sister_weapons()
        return self.get_riven_items()

    def get_riven_attributes(self) -> list[RivenAttribute]:
        try:
            data = self._request("GET", "/v2/riven/attributes")
            attrs = extract_riven_attributes(data)
            if attrs:
                return attrs
        except Exception as exc:
            logger.warning("Failed to fetch riven attributes from v2 API: %s", exc)

        try:
            data = self._request("GET", "/riven/attributes")
            attrs = extract_riven_attributes(data)
            if attrs:
                return attrs
        except Exception as exc:
            logger.warning("Failed to fetch riven attributes from v1 API: %s", exc)

        logger.info("Using fallback static riven attributes list")
        return FALLBACK_RIVEN_ATTRIBUTES

    def search_auctions(
        self,
        type_: str = "riven",
        weapon_url_name: str | None = None,
        positive_stats: str | list[str] | None = None,
        sort_by: str | None = None,
        element: str | None = None,
        having_ephemera: bool | None = None,
        quirk: str | None = None,
    ) -> list[AuctionItem]:
        api_type = "lich" if type_ in ("kuva_lich", "lich") else ("sister" if type_ in ("sister_of_parvos", "sister") else "riven")
        path = f"/auctions/search?type={api_type}"
        if weapon_url_name and weapon_url_name != "*":
            path += f"&weapon_url_name={weapon_url_name}"
        if positive_stats and api_type == "riven":
            if isinstance(positive_stats, (list, tuple, set)):
                stats_str = ",".join(positive_stats)
            else:
                stats_str = str(positive_stats)
            if stats_str:
                path += f"&positive_stats={stats_str}"
        if element and element != "any":
            path += f"&element={element}"
        if having_ephemera is not None:
            path += f"&having_ephemera={'true' if having_ephemera else 'false'}"
        if quirk and quirk not in ("any", "none"):
            path += f"&quirk={quirk}"
        if sort_by:
            path += f"&sort_by={sort_by}"
        data = self._request("GET", path)
        return extract_auctions(data)

    def send_chat_message(self, chat_id: str, text: str) -> None:
        try:
            import websocket
        except ImportError as exc:
            raise WarframeMarketError(
                "Sending Telegram replies requires the websocket-client package"
            ) from exc

        payload = {
            "type": "@WS/chats/SEND_MESSAGE",
            "payload": {
                "chat_id": chat_id,
                "message": text,
                "temp_id": secrets.token_hex(12),
            },
        }
        headers = [
            f"Origin: {self.config.market_base_url}",
            "User-Agent: market-message/0.1",
        ]
        cookie_header = self._cookie_header()
        if cookie_header:
            headers.append(f"Cookie: {cookie_header}")

        try:
            socket = websocket.create_connection(
                _websocket_url(self.config.market_base_url, self.config.platform),
                timeout=self.config.request_timeout_seconds,
                header=headers,
                subprotocols=["wfm"],
            )
            try:
                socket.send(json.dumps(payload))
            finally:
                socket.close()
        except Exception as exc:
            raise WarframeMarketError("Warframe Market WebSocket send failed") from exc

    def _rate_limit(self) -> None:
        if self._max_rps <= 0 and self._max_rpm <= 0:
            return
        with self._rate_limit_lock:
            while True:
                now = time.monotonic()
                self._request_timestamps = [t for t in self._request_timestamps if now - t < 60.0]

                wait_time = 0.0

                if self._max_rpm > 0 and len(self._request_timestamps) >= self._max_rpm:
                    oldest_in_minute = self._request_timestamps[len(self._request_timestamps) - int(self._max_rpm)]
                    wait_time = max(wait_time, 60.0 - (now - oldest_in_minute))

                recent_1s = [t for t in self._request_timestamps if now - t < 1.0]
                if self._max_rps > 0 and len(recent_1s) >= self._max_rps:
                    oldest_in_second = recent_1s[len(recent_1s) - int(self._max_rps)]
                    wait_time = max(wait_time, 1.0 - (now - oldest_in_second))
                elif self._min_request_interval > 0 and self._request_timestamps:
                    elapsed = now - self._request_timestamps[-1]
                    if elapsed < self._min_request_interval:
                        wait_time = max(wait_time, self._min_request_interval - elapsed)

                if wait_time > 0.0001:
                    time.sleep(wait_time)
                else:
                    self._request_timestamps.append(time.monotonic())
                    break

    def _send_request(self, method: str, url: str, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        max_retries = 3
        req_headers = headers if headers is not None else {}
        for attempt in range(max_retries + 1):
            self._rate_limit()
            response = self._client.request(method, url, headers=req_headers, **kwargs)
            if response.status_code == 429 and attempt < max_retries:
                retry_after_str = response.headers.get("Retry-After")
                try:
                    retry_after = float(retry_after_str) if retry_after_str else 2.0
                except ValueError:
                    retry_after = 2.0
                logger.warning(
                    "Warframe Market returned 429 Too Many Requests for %s %s. Retrying in %.1fs (attempt %d/%d)...",
                    method,
                    url,
                    retry_after,
                    attempt + 1,
                    max_retries,
                )
                time.sleep(retry_after)
                continue
            return response
        return response

    def _fetch_csrf_token(self) -> str:
        try:
            init_res = self._send_request("GET", f"{self.config.api_base_url}/auctions/search")
            jwt_token = self._client.cookies.get("JWT")
            if jwt_token:
                return jwt_token
        except Exception:
            pass

        response = self._send_request("GET", self.config.market_base_url)
        if (
            response.status_code == 403
            or "Just a moment..." in response.text
            or "challenge-platform" in response.text
        ):
            raise AuthenticationError(
                "Warframe Market website (warframe.market) returned 403 Forbidden due to Cloudflare Bot Protection. "
                "Direct scraping of the CSRF token from warframe.market HTML is blocked by Cloudflare. "
                "Please set WARFRAME_MARKET_JWT_TOKEN (your browser JWT session cookie) or WARFRAME_MARKET_CSRF_TOKEN in your .env file."
            )
        response.raise_for_status()
        parser = _CsrfParser()
        parser.feed(response.text)
        if not parser.csrf_token:
            raise WarframeMarketError("Unable to find CSRF token on Warframe Market page")
        return parser.csrf_token

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        csrf = bool(kwargs.pop("csrf", False))
        headers = {
            "Accept": "application/json",
            "Platform": self.config.platform,
            "Language": self.config.language,
            "platform": self.config.platform,
            "language": self.config.language,
            "crossplay": str(self.config.crossplay).lower(),
        }
        if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            headers["Content-Type"] = "application/json"
        jwt_token = getattr(self.config, "warframe_jwt_token", "")
        if jwt_token:
            auth_val = jwt_token if jwt_token.startswith("JWT ") or jwt_token.startswith("Bearer ") else f"JWT {jwt_token}"
            headers["Authorization"] = auth_val
        if csrf and self._csrf_token:
            headers["X-CSRFToken"] = self._csrf_token

        if path.startswith("/v2/"):
            base_url = self.config.api_base_url
            if "/v1" in base_url:
                base_url = base_url.split("/v1")[0]
            url = f"{base_url}{path}"
        else:
            url = f"{self.config.api_base_url}{path}"
        response = self._send_request(method, url, headers=headers, **kwargs)
        if response.status_code in {401, 403}:
            if "Just a moment..." in response.text or "challenge-platform" in response.text:
                raise AuthenticationError(
                    "Warframe Market returned 403 Forbidden (Cloudflare Bot Protection). "
                    "Please set WARFRAME_MARKET_JWT_TOKEN in your .env file."
                )
            raise AuthenticationError(f"Warframe Market returned {response.status_code}")
        if response.status_code >= 400:
            raise WarframeMarketError(
                f"Warframe Market returned {response.status_code}: {response.text[:500]}"
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise WarframeMarketError("Warframe Market returned non-JSON response") from exc
        if not isinstance(data, dict):
            raise WarframeMarketError("Warframe Market returned unexpected JSON shape")
        return data

    def _cookie_header(self) -> str:
        return "; ".join(
            f"{cookie.name}={cookie.value}"
            for cookie in self._client.cookies.jar
        )


def extract_user_id_from_chats(data: dict[str, Any]) -> str | None:
    if not isinstance(data, dict):
        return None
    payload = _unwrap_payload(data)
    user = payload.get("user") or data.get("user")
    if isinstance(user, dict) and user.get("id"):
        return str(user["id"])
    my_id = payload.get("my_id") or payload.get("current_user_id")
    if my_id:
        return str(my_id)
    return None


def extract_chats(data: dict[str, Any]) -> list[ChatSummary]:
    payload = _unwrap_payload(data)
    raw_chats = _extract_collection(payload, "chats")
    chats: list[ChatSummary] = []
    for raw_chat in raw_chats:
        if not isinstance(raw_chat, dict):
            continue
        chat_id = raw_chat.get("id") or raw_chat.get("chat_id") or raw_chat.get("_id")
        if not chat_id:
            continue
        unread = raw_chat.get("unread_count", raw_chat.get("unread_messages", 0))
        chats.append(ChatSummary(id=str(chat_id), unread_count=_safe_int(unread)))
    return chats


def extract_messages(data: dict[str, Any], chat_id: str) -> list[IncomingMessage]:
    payload = _unwrap_payload(data)
    raw_messages = _extract_collection(payload, "messages")
    users = _extract_users(payload)
    messages: list[IncomingMessage] = []

    for raw_message in raw_messages:
        if not isinstance(raw_message, dict):
            continue
        message_id = raw_message.get("id") or raw_message.get("_id") or raw_message.get("temp_id")
        sender_id = (
            raw_message.get("message_from")
            or raw_message.get("from")
            or raw_message.get("sender_id")
            or raw_message.get("user_id")
        )
        if not message_id or not sender_id:
            continue
        message_chat_id = raw_message.get("chat_id") or chat_id
        text = raw_message.get("raw_message")
        if text is None:
            text = raw_message.get("message", raw_message.get("text", ""))
        sender_name = _sender_name(raw_message, users, str(sender_id))
        messages.append(
            IncomingMessage(
                id=str(message_id),
                chat_id=str(message_chat_id),
                sender_id=str(sender_id),
                sender_name=sender_name,
                text=str(text),
                sent_at=_optional_str(
                    raw_message.get("send_date")
                    or raw_message.get("created_at")
                    or raw_message.get("created")
                ),
            )
        )

    return messages


def _unwrap_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload = data.get("payload", data)
    return payload if isinstance(payload, dict) else {}


def _extract_collection(payload: dict[str, Any], name: str) -> list[Any]:
    direct = payload.get(name)
    if isinstance(direct, list):
        return direct
    if isinstance(direct, dict):
        return list(direct.values())

    entities = payload.get("entities")
    if isinstance(entities, dict):
        entity_collection = entities.get(name)
        if isinstance(entity_collection, dict):
            result = payload.get("result")
            if isinstance(result, list):
                return [
                    entity_collection[item_id]
                    for item_id in result
                    if item_id in entity_collection
                ]
            return list(entity_collection.values())

    return []


def _extract_users(payload: dict[str, Any]) -> dict[str, Any]:
    users = payload.get("users")
    if isinstance(users, dict):
        return users
    entities = payload.get("entities")
    if isinstance(entities, dict) and isinstance(entities.get("users"), dict):
        return entities["users"]
    return {}


def _sender_name(raw_message: dict[str, Any], users: dict[str, Any], sender_id: str) -> str:
    sender = raw_message.get("sender")
    if isinstance(sender, dict):
        name = sender.get("ingame_name") or sender.get("ingameName") or sender.get("slug")
        if name:
            return str(name)
    user = users.get(sender_id)
    if isinstance(user, dict):
        name = user.get("ingame_name") or user.get("ingameName") or user.get("slug")
        if name:
            return str(name)
    return sender_id


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _websocket_url(market_base_url: str, platform: str) -> str:
    parsed = urlparse(market_base_url)
    host = parsed.hostname or "warframe.market"
    scheme = "wss" if parsed.scheme != "http" else "ws"
    return f"{scheme}://ws.{host}/socket?platform={platform}"


class _CsrfParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.csrf_token: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        attr_map = {key: value for key, value in attrs}
        if attr_map.get("name") == "csrf-token" and attr_map.get("content"):
            self.csrf_token = attr_map["content"]


def _extract_i18n_name(i18n_data: Any, preferred_lang: str = "ru") -> str | None:
    if not isinstance(i18n_data, dict):
        return None
    for lang in (preferred_lang, "en"):
        entry = i18n_data.get(lang)
        if isinstance(entry, dict) and entry.get("name"):
            return str(entry["name"])
    for entry in i18n_data.values():
        if isinstance(entry, dict) and entry.get("name"):
            return str(entry["name"])
    return None


def _extract_i18n_icon(i18n_data: Any) -> str | None:
    if not isinstance(i18n_data, dict):
        return None
    for lang in ("en", "ru"):
        entry = i18n_data.get(lang)
        if isinstance(entry, dict) and entry.get("icon"):
            return str(entry["icon"])
    return None


def extract_riven_items(data: dict[str, Any]) -> list[RivenItem]:
    payload = _unwrap_payload(data)
    items_raw = _extract_collection(payload, "items")
    if not items_raw and isinstance(data, dict):
        raw_data = data.get("data")
        if isinstance(raw_data, list):
            items_raw = raw_data

    result: list[RivenItem] = []
    for item in items_raw:
        if not isinstance(item, dict):
            continue
        url_name = item.get("url_name") or item.get("slug")
        item_name = (
            item.get("item_name")
            or item.get("name")
            or _extract_i18n_name(item.get("i18n"))
            or url_name
        )
        if not url_name or not item_name:
            continue
        riven_type = _optional_str(item.get("riven_type") or item.get("rivenType"))
        icon = _optional_str(item.get("icon") or _extract_i18n_icon(item.get("i18n")))

        ru_name = None
        i18n = item.get("i18n")
        if isinstance(i18n, dict) and isinstance(i18n.get("ru"), dict) and i18n["ru"].get("name"):
            ru_name = str(i18n["ru"]["name"])
        if not ru_name:
            ru_name = WEAPON_RU_NAMES.get(str(url_name))

        result.append(
            RivenItem(
                url_name=str(url_name),
                item_name=str(item_name),
                group=str(item.get("group", "primary")),
                riven_type=riven_type,
                icon=icon,
                ru_name=ru_name,
            )
        )
    return result


def extract_riven_attributes(data: dict[str, Any]) -> list[RivenAttribute]:
    payload = _unwrap_payload(data)
    attrs_raw = _extract_collection(payload, "attributes")
    if not attrs_raw and isinstance(data, dict):
        raw_data = data.get("data")
        if isinstance(raw_data, list):
            attrs_raw = raw_data

    result: list[RivenAttribute] = []
    for attr in attrs_raw:
        if not isinstance(attr, dict):
            continue
        url_name = attr.get("url_name") or attr.get("slug")
        effect = (
            attr.get("effect")
            or attr.get("name")
            or _extract_i18n_name(attr.get("i18n"))
            or url_name
        )
        if not url_name or not effect:
            continue
        result.append(
            RivenAttribute(
                url_name=str(url_name),
                effect=str(effect),
                units=_optional_str(attr.get("units")),
                positive_is_negative=bool(attr.get("positive_is_negative", False)),
                group=_optional_str(attr.get("group")),
            )
        )
    return result


def extract_auctions(data: dict[str, Any]) -> list[AuctionItem]:
    payload = _unwrap_payload(data)
    auctions_raw = _extract_collection(payload, "auctions")
    result: list[AuctionItem] = []

    for auction in auctions_raw:
        if not isinstance(auction, dict):
            continue
        auction_id = auction.get("id") or auction.get("_id")
        item_dict = auction.get("item")
        owner_dict = auction.get("owner")
        if not auction_id or not isinstance(item_dict, dict) or not isinstance(owner_dict, dict):
            continue

        weapon_url_name = item_dict.get("weapon_url_name") or item_dict.get("url_name") or "*"
        riven_name = item_dict.get("name") or item_dict.get("riven_name") or weapon_url_name
        item_type = str(item_dict.get("type") or "riven")
        element = _optional_str(item_dict.get("element"))
        damage = item_dict.get("damage")
        having_ephemera = bool(item_dict.get("having_ephemera", False))
        ephemera = _optional_str(item_dict.get("ephemera"))
        quirk = _optional_str(item_dict.get("quirk"))
        
        attributes_raw = item_dict.get("attributes") or []
        parsed_attrs: list[AuctionAttribute] = []
        for attr in attributes_raw:
            if isinstance(attr, dict) and "url_name" in attr and "value" in attr:
                parsed_attrs.append(
                    AuctionAttribute(
                        url_name=str(attr["url_name"]),
                        positive=bool(attr.get("positive", True)),
                        value=float(attr["value"]),
                    )
                )

        rerolls = item_dict.get("rerolls")
        if rerolls is None:
            rerolls = item_dict.get("re_rolls", 0)

        seller_name = (
            owner_dict.get("ingame_name")
            or owner_dict.get("ingameName")
            or owner_dict.get("slug")
            or "Unknown"
        )
        seller_status = owner_dict.get("status") or "offline"

        buyout_price = auction.get("buyout_price")
        starting_price = auction.get("starting_price")

        result.append(
            AuctionItem(
                id=str(auction_id),
                weapon_url_name=str(weapon_url_name),
                riven_name=str(riven_name),
                attributes=parsed_attrs,
                buyout_price=int(buyout_price) if buyout_price is not None else None,
                starting_price=int(starting_price) if starting_price is not None else None,
                rerolls=_safe_int(rerolls),
                mastery_rank=_safe_int(item_dict.get("mastery_rank", 0)),
                polarity=str(item_dict.get("polarity", "universal")),
                seller_name=str(seller_name),
                seller_status=str(seller_status),
                is_direct_sell=bool(auction.get("is_direct_sell", True)),
                created_at=_optional_str(auction.get("created")),
                updated_at=_optional_str(auction.get("updated")),
                item_type=item_type,
                element=element,
                damage=float(damage) if damage is not None else None,
                having_ephemera=having_ephemera,
                ephemera=ephemera,
                quirk=quirk,
            )
        )

    return result

