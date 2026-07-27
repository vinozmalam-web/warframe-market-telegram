from __future__ import annotations

import logging
from typing import Any

from .models import AuctionItem, SniperRule
from .state import StateStore
from .telegram import TelegramClient
from .warframe import WarframeMarketClient

logger = logging.getLogger(__name__)


def matches_rule(rule: SniperRule, auction: AuctionItem) -> bool:
    if not rule.is_active:
        return False

    # 1. Weapon check
    if rule.weapon_url_name and rule.weapon_url_name != "*":
        if rule.weapon_url_name.lower() != auction.weapon_url_name.lower():
            return False

    # 2. Price check
    price = auction.buyout_price if auction.buyout_price is not None else auction.starting_price
    if price is None:
        if rule.max_price is not None:
            return False
    else:
        if rule.min_price is not None and price < rule.min_price:
            return False
        if rule.max_price is not None and price > rule.max_price:
            return False

    # 3. Rerolls check
    if rule.min_rerolls is not None and auction.rerolls < rule.min_rerolls:
        return False
    if rule.max_rerolls is not None and auction.rerolls > rule.max_rerolls:
        return False

    # 4. Seller status check
    if rule.seller_status == "ingame" and auction.seller_status != "ingame":
        return False
    if rule.seller_status == "online" and auction.seller_status not in {"ingame", "online"}:
        return False

    # 5. Positive stats check
    pos_attrs = {attr.url_name: attr.value for attr in auction.attributes if attr.positive}
    for req in rule.positive_stats:
        url_name = req.get("url_name")
        if not url_name:
            continue
        if url_name not in pos_attrs:
            return False
        val = pos_attrs[url_name]
        min_val = req.get("min_value")
        max_val = req.get("max_value")
        if min_val is not None and val < float(min_val):
            return False
        if max_val is not None and val > float(max_val):
            return False

    # 6. Negative stat check
    neg_attrs = [attr for attr in auction.attributes if not attr.positive]
    neg_rule = rule.negative_stat or {}
    mode = neg_rule.get("mode", "any_or_none")  # "none", "any", "specific", "any_or_none"

    if mode == "none":
        if len(neg_attrs) > 0:
            return False
    elif mode == "any":
        if len(neg_attrs) == 0:
            return False
    elif mode == "specific":
        target_url = neg_rule.get("url_name")
        if not target_url:
            return False
        matching = [a for a in neg_attrs if a.url_name == target_url]
        if not matching:
            return False
        val = matching[0].value
        min_val = neg_rule.get("min_value")
        max_val = neg_rule.get("max_value")
        # Handle magnitude comparison if stats are negative floats (e.g. -45.0)
        abs_val = abs(val)
        if min_val is not None and abs_val < abs(float(min_val)):
            return False
        if max_val is not None and abs_val > abs(float(max_val)):
            return False

    return True


def format_stat_name(url_name: str) -> str:
    clean = url_name.replace("_", " ").title()
    return clean


def format_riven_notification(auction: AuctionItem, rule: SniperRule, market_base_url: str) -> str:
    price_str = f"{auction.buyout_price} 💎" if auction.buyout_price is not None else (
        f"{auction.starting_price} 💎 (Аукцион)" if auction.starting_price is not None else "Н/Д"
    )
    status_emoji = "🟢" if auction.seller_status == "ingame" else ("🟡" if auction.seller_status == "online" else "⚪")
    
    attr_lines = []
    for attr in auction.attributes:
        sign = "+" if attr.positive else "-"
        val_str = f"{abs(attr.value):.1f}"
        name = format_stat_name(attr.url_name)
        emoji = "✨" if attr.positive else "🔻"
        attr_lines.append(f"{emoji} <code>{sign}{val_str}% {name}</code>")

    stats_block = "\n".join(attr_lines) if attr_lines else "<i>Нет характеристик</i>"
    whisper_cmd = f"/w {auction.seller_name} Hi! WTB your [{auction.riven_name}] for {auction.buyout_price or auction.starting_price or 0}p (warframe.market)"
    auction_url = f"{market_base_url}/auction/{auction.id}"

    return (
        f"🎯 <b>СНАЙПЕР: Найден Riven!</b>\n"
        f"📋 <b>Правило</b>: <i>{_escape_html(rule.name)}</i>\n\n"
        f"🔫 <b>Оружие</b>: <b>{_escape_html(auction.riven_name.title())}</b>\n"
        f"💰 <b>Цена</b>: <b>{price_str}</b>\n"
        f"👤 <b>Продавец</b>: {status_emoji} <b>{_escape_html(auction.seller_name)}</b> ({auction.seller_status})\n"
        f"🔄 <b>Роллы</b>: {auction.rerolls} | <b>MR</b>: {auction.mastery_rank} | <b>Полярность</b>: {auction.polarity.title()}\n\n"
        f"📊 <b>Характеристики</b>:\n{stats_block}\n\n"
        f"💬 <b>Нажми, чтобы скопировать шёпот</b>:\n"
        f"<pre><code>{_escape_html(whisper_cmd)}</code></pre>\n\n"
        f"🔗 <a href=\"{auction_url}\">Открыть на Warframe.Market</a>"
    )


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


class RivenSniperEngine:
    def __init__(
        self,
        warframe: WarframeMarketClient,
        telegram: TelegramClient,
        state: StateStore,
        market_base_url: str,
    ):
        self.warframe = warframe
        self.telegram = telegram
        self.state = state
        self.market_base_url = market_base_url

    def check_auctions_once(self) -> int:
        rules = [r for r in self.state.get_sniper_rules() if r.is_active]
        if not rules:
            return 0

        # Group rules by target weapon url name to minimize API requests
        weapon_groups: dict[str, list[SniperRule]] = {}
        for rule in rules:
            w_name = rule.weapon_url_name if rule.weapon_url_name else "*"
            weapon_groups.setdefault(w_name, []).append(rule)

        notified_count = 0
        for w_name, group_rules in weapon_groups.items():
            try:
                auctions = self.warframe.search_auctions(type_="riven", weapon_url_name=w_name)
            except Exception as exc:
                logger.warning("Failed to search riven auctions for weapon '%s': %s", w_name, exc)
                continue

            for auction in auctions:
                if self.state.was_auction_seen(auction.id):
                    continue

                for rule in group_rules:
                    if matches_rule(rule, auction):
                        msg = format_riven_notification(auction, rule, self.market_base_url)
                        try:
                            self.telegram.send_message(msg, parse_mode="HTML")
                            self.state.mark_auction_seen(auction.id, rule.id)
                            notified_count += 1
                            logger.info(
                                "Sniper alert sent for auction %s (rule: %s, weapon: %s)",
                                auction.id,
                                rule.name,
                                auction.riven_name,
                            )
                            break
                        except Exception as exc:
                            logger.exception("Failed to send telegram notification for auction %s: %s", auction.id, exc)

        return notified_count
