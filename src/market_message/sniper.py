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

    rule_type = "lich" if rule.item_type in ("kuva_lich", "lich") else ("sister" if rule.item_type in ("sister_of_parvos", "sister") else "riven")
    auction_type = "lich" if auction.item_type in ("kuva_lich", "lich") else ("sister" if auction.item_type in ("sister_of_parvos", "sister") else "riven")
    if rule_type != auction_type:
        return False

    # Buyout policy / auction exclusion check
    if rule.buyout_policy == "direct":
        if auction.buyout_price is None or not auction.is_direct_sell:
            return False
    elif rule.buyout_policy == "auction":
        if auction.buyout_price is not None and auction.is_direct_sell:
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

    # 3. Seller status check
    if rule.seller_status == "ingame" and auction.seller_status != "ingame":
        return False
    if rule.seller_status == "online" and auction.seller_status not in {"ingame", "online"}:
        return False

    if rule_type == "riven":
        # 4. Rerolls check
        if rule.min_rerolls is not None and auction.rerolls < rule.min_rerolls:
            return False
        if rule.max_rerolls is not None and auction.rerolls > rule.max_rerolls:
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
        mode = neg_rule.get("mode", "any_or_none")

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
            abs_val = abs(val)
            if min_val is not None and abs_val < abs(float(min_val)):
                return False
            if max_val is not None and abs_val > abs(float(max_val)):
                return False
    else:
        # Lich / Sister checks
        if rule.element and rule.element not in ("any", "*"):
            if not auction.element or auction.element.lower() != rule.element.lower():
                return False

        if rule.min_damage is not None:
            if auction.damage is None or auction.damage < float(rule.min_damage):
                return False

        if rule.ephemera_filter == "yes" and not auction.having_ephemera:
            return False
        if rule.ephemera_filter == "no" and auction.having_ephemera:
            return False

        if rule.quirk and rule.quirk not in ("any", "*"):
            if rule.quirk == "none":
                if auction.quirk and auction.quirk not in ("none", ""):
                    return False
            else:
                if not auction.quirk or auction.quirk.lower() != rule.quirk.lower():
                    return False

    return True


def format_stat_name(url_name: str) -> str:
    clean = url_name.replace("_", " ").title()
    return clean


ELEMENT_EMOJIS = {
    "heat": "🔥",
    "toxin": "🧪",
    "cold": "❄️",
    "electricity": "⚡",
    "magnetic": "🧲",
    "radiation": "☢️",
    "impact": "💥",
}


def format_riven_notification(
    auction: AuctionItem,
    rule: SniperRule,
    market_base_url: str,
    old_price: int | None = None,
) -> str:
    current_price = auction.buyout_price if auction.buyout_price is not None else auction.starting_price
    if current_price is not None:
        if old_price is not None and old_price > current_price:
            price_str = f"{current_price} 💎 <i>(📉 было {old_price} 💎)</i>"
        else:
            price_str = f"{current_price} 💎" if auction.buyout_price is not None else f"{auction.starting_price} 💎 (Аукцион)"
    else:
        price_str = "Н/Д"

    status_emoji = "🟢" if auction.seller_status == "ingame" else ("🟡" if auction.seller_status == "online" else "⚪")
    auction_url = f"{market_base_url}/auction/{auction.id}"

    rule_type = "lich" if rule.item_type in ("kuva_lich", "lich") else ("sister" if rule.item_type in ("sister_of_parvos", "sister") else "riven")

    if rule_type == "riven":
        header_title = "📉 <b>СНАЙПЕР: Снижение цены на Riven!</b>" if (old_price is not None and current_price is not None and old_price > current_price) else "🎯 <b>СНАЙПЕР: Найден Riven!</b>"
        attr_lines = []
        for attr in auction.attributes:
            sign = "+" if attr.positive else "-"
            val_str = f"{abs(attr.value):.1f}"
            name = format_stat_name(attr.url_name)
            emoji = "✨" if attr.positive else "🔻"
            attr_lines.append(f"{emoji} <b>{sign}{val_str}% {name}</b>")

        stats_block = "\n".join(attr_lines) if attr_lines else "<i>Нет характеристик</i>"
        weapon_display = auction.weapon_url_name.replace("_", " ").title() if auction.weapon_url_name and auction.weapon_url_name != "*" else ""
        riven_display = (auction.riven_name or "").strip()
        weapon_words = [w.lower() for w in weapon_display.split() if len(w) >= 3]
        already_has_weapon = any(w in riven_display.lower() for w in weapon_words) if weapon_words else False

        if already_has_weapon:
            full_riven_name = riven_display.title()
        elif weapon_display and riven_display:
            full_riven_name = f"{weapon_display} {riven_display}".title()
        else:
            full_riven_name = (riven_display or weapon_display).title()

        whisper_cmd = f"/w {auction.seller_name} Hi! WTB your {full_riven_name} for {auction.buyout_price or auction.starting_price or 0}p (warframe.market)"

        return (
            f"{header_title}\n"
            f"📋 <b>Правило</b>: <i>{_escape_html(rule.name)}</i>\n\n"
            f"🔫 <b>Оружие</b>: <b>{_escape_html(full_riven_name)}</b>\n"
            f"💰 <b>Цена</b>: <b>{price_str}</b>\n"
            f"👤 <b>Продавец</b>: {status_emoji} <b>{_escape_html(auction.seller_name)}</b> ({auction.seller_status})\n"
            f"🔄 <b>Роллы</b>: {auction.rerolls} | <b>MR</b>: {auction.mastery_rank} | <b>Полярность</b>: {auction.polarity.title()}\n\n"
            f"📊 <b>Характеристики</b>:\n{stats_block}\n\n"
            f"💬 <b>Нажми, чтобы скопировать шёпот</b>:\n"
            f"<pre><code>{_escape_html(whisper_cmd)}</code></pre>\n\n"
            f"🔗 <a href=\"{auction_url}\">Открыть на Warframe.Market</a>"
        )
    else:
        type_title = "Кува Лич" if rule_type == "lich" else "Сестра Парвоса"
        header_title = f"📉 <b>СНАЙПЕР: Снижение цены ({type_title})!</b>" if (old_price is not None and current_price is not None and old_price > current_price) else f"🎯 <b>СНАЙПЕР: Найден {type_title}!</b>"
        weapon_display = auction.weapon_url_name.replace("_", " ").title()
        elem_name = (auction.element or "Неизвестно").title()
        elem_emoji = ELEMENT_EMOJIS.get(str(auction.element).lower(), "⚡")
        damage_str = f"{auction.damage:.1f}%" if auction.damage is not None else "Н/Д"
        eph_str = "Да ✨" if auction.having_ephemera else "Нет ❌"
        quirk_str = auction.quirk.replace("_", " ").title() if auction.quirk and auction.quirk != "none" else "Отсутствует"

        whisper_cmd = f"/w {auction.seller_name} Hi! WTB your [{weapon_display}] ({elem_name} {damage_str}) for {auction.buyout_price or auction.starting_price or 0}p (warframe.market)"

        return (
            f"{header_title}\n"
            f"📋 <b>Правило</b>: <i>{_escape_html(rule.name)}</i>\n\n"
            f"🔫 <b>Оружие</b>: <b>{_escape_html(weapon_display)}</b>\n"
            f"⚡ <b>Стихия</b>: {elem_emoji} <b>{elem_name} ({damage_str})</b>\n"
            f"✨ <b>Эфемера</b>: <b>{eph_str}</b>\n"
            f"🎭 <b>Особенность (Quirk)</b>: {quirk_str}\n"
            f"💰 <b>Цена</b>: <b>{price_str}</b>\n"
            f"👤 <b>Продавец</b>: {status_emoji} <b>{_escape_html(auction.seller_name)}</b> ({auction.seller_status})\n\n"
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
        max_alerts_per_rule_run: int = 3,
        seen_auction_ttl_days: int = 7,
    ):
        self.warframe = warframe
        self.telegram = telegram
        self.state = state
        self.market_base_url = market_base_url
        self.max_alerts_per_rule_run = max_alerts_per_rule_run
        self.seen_auction_ttl_days = seen_auction_ttl_days

    def check_auctions_once(self) -> int:
        try:
            self.state.cleanup_old_seen_auctions(self.seen_auction_ttl_days)
        except Exception as exc:
            logger.warning("Failed to clean up old seen auctions: %s", exc)

        rules = [r for r in self.state.get_sniper_rules() if r.is_active]
        if not rules:
            return 0

        # Group rules by (item_type, target weapon url name) to minimize API requests
        weapon_groups: dict[tuple[str, str], list[SniperRule]] = {}
        for rule in rules:
            w_name = rule.weapon_url_name if rule.weapon_url_name else "*"
            weapon_groups.setdefault((rule.item_type, w_name), []).append(rule)

        notified_count = 0
        for (item_type, w_name), group_rules in weapon_groups.items():
            if w_name == "*" or not w_name:
                logger.warning(
                    "Skipping wildcard weapon ('*') search for %s to prevent Warframe Market API rate limits. Rule names: %s",
                    item_type,
                    [r.name for r in group_rules],
                )
                continue

            auctions: list[AuctionItem] = []
            try:
                auctions = self.warframe.search_auctions(type_=item_type, weapon_url_name=w_name)
            except Exception as exc:
                logger.warning("Failed to search %s auctions for weapon '%s': %s", item_type, w_name, exc)
                continue

            for rule in group_rules:
                unseen_matches = []
                auction_old_prices: dict[str, int | None] = {}
                for auction in auctions:
                    auction_price = auction.buyout_price if auction.buyout_price is not None else auction.starting_price
                    if self.state.was_auction_seen(auction.id, price=auction_price):
                        continue
                    old_price = self.state.get_seen_auction_price(auction.id)
                    if matches_rule(rule, auction):
                        unseen_matches.append(auction)
                        auction_old_prices[auction.id] = old_price
                    else:
                        self.state.mark_auction_seen(auction.id, rule.id, price=auction_price)

                if not unseen_matches:
                    continue

                send_batch = unseen_matches[: self.max_alerts_per_rule_run]
                skipped_batch = unseen_matches[self.max_alerts_per_rule_run :]

                for auction in send_batch:
                    auction_price = auction.buyout_price if auction.buyout_price is not None else auction.starting_price
                    old_price = auction_old_prices.get(auction.id)
                    msg = format_riven_notification(auction, rule, self.market_base_url, old_price=old_price)
                    try:
                        self.telegram.send_message(msg, parse_mode="HTML")
                        self.state.mark_auction_seen(auction.id, rule.id, price=auction_price)
                        notified_count += 1
                        logger.info(
                            "Sniper alert sent for auction %s (rule: %s, weapon: %s, price: %s)",
                            auction.id,
                            rule.name,
                            auction.riven_name,
                            auction_price,
                        )
                    except Exception as exc:
                        logger.exception("Failed to send telegram notification for auction %s: %s", auction.id, exc)

                if skipped_batch:
                    for auction in skipped_batch:
                        auction_price = auction.buyout_price if auction.buyout_price is not None else auction.starting_price
                        self.state.mark_auction_seen(auction.id, rule.id, price=auction_price)

                    summary_msg = (
                        f"ℹ️ <b>Снайпер: Сработало широкое правило</b>\n"
                        f"📋 <b>Правило</b>: <i>{_escape_html(rule.name)}</i>\n"
                        f"📊 Найдено совпадений: <b>{len(unseen_matches)}</b>\n"
                        f"Отправлено первых <b>{len(send_batch)}</b> уведомлений. "
                        f"Остальные <b>{len(skipped_batch)}</b> отмечены как просмотренные для защиты от спама."
                    )
                    try:
                        self.telegram.send_message(summary_msg, parse_mode="HTML")
                    except Exception as exc:
                        logger.exception("Failed to send summary message: %s", exc)

        return notified_count
