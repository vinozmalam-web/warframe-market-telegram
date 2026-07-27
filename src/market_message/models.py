from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChatSummary:
    id: str
    unread_count: int


@dataclass(frozen=True)
class IncomingMessage:
    id: str
    chat_id: str
    sender_id: str
    sender_name: str
    text: str
    sent_at: str | None


@dataclass(frozen=True)
class TelegramIncomingMessage:
    message_id: int
    chat_id: str
    text: str | None
    reply_to_message_id: int | None


@dataclass(frozen=True)
class TelegramUpdate:
    update_id: int
    message: TelegramIncomingMessage | None


@dataclass(frozen=True)
class RivenAttribute:
    url_name: str
    effect: str
    units: str | None = None
    positive_is_negative: bool = False
    group: str | None = None


@dataclass(frozen=True)
class RivenItem:
    url_name: str
    item_name: str
    group: str
    riven_type: str | None = None
    icon: str | None = None
    ru_name: str | None = None


@dataclass(frozen=True)
class AuctionAttribute:
    url_name: str
    positive: bool
    value: float


@dataclass(frozen=True)
class AuctionItem:
    id: str
    weapon_url_name: str
    riven_name: str = ""
    attributes: list[AuctionAttribute] = field(default_factory=list)
    buyout_price: int | None = None
    starting_price: int | None = None
    rerolls: int = 0
    mastery_rank: int = 0
    polarity: str = "universal"
    seller_name: str = "Unknown"
    seller_status: str = "offline"
    is_direct_sell: bool = True
    created_at: str | None = None
    updated_at: str | None = None
    item_type: str = "riven"
    element: str | None = None
    damage: float | None = None
    having_ephemera: bool = False
    ephemera: str | None = None
    quirk: str | None = None


@dataclass
class SniperRule:
    id: int | None = None
    name: str = ""
    item_type: str = "riven"
    weapon_url_name: str = "*"
    target_name: str = "Any Weapon"
    min_price: int | None = None
    max_price: int | None = None
    min_rerolls: int | None = None
    max_rerolls: int | None = None
    seller_status: str = "any"
    positive_stats: list[dict] = field(default_factory=list)
    negative_stat: dict = field(default_factory=dict)
    is_active: bool = True
    element: str = "any"
    min_damage: float | int | None = None
    ephemera_filter: str = "any"
    quirk: str = "any"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "item_type": self.item_type,
            "weapon_url_name": self.weapon_url_name,
            "target_name": self.target_name,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "min_rerolls": self.min_rerolls,
            "max_rerolls": self.max_rerolls,
            "seller_status": self.seller_status,
            "positive_stats": self.positive_stats,
            "negative_stat": self.negative_stat,
            "is_active": self.is_active,
            "element": self.element,
            "min_damage": self.min_damage,
            "ephemera_filter": self.ephemera_filter,
            "quirk": self.quirk,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SniperRule":
        return cls(
            id=data.get("id"),
            name=data.get("name") or "Unnamed Rule",
            item_type=data.get("item_type") or "riven",
            weapon_url_name=data.get("weapon_url_name") or "*",
            target_name=data.get("target_name") or "Any Weapon",
            min_price=data.get("min_price"),
            max_price=data.get("max_price"),
            min_rerolls=data.get("min_rerolls"),
            max_rerolls=data.get("max_rerolls"),
            seller_status=data.get("seller_status") or "any",
            positive_stats=data.get("positive_stats") or [],
            negative_stat=data.get("negative_stat") or {},
            is_active=data.get("is_active", True),
            element=data.get("element") or "any",
            min_damage=data.get("min_damage"),
            ephemera_filter=data.get("ephemera_filter") or "any",
            quirk=data.get("quirk") or "any",
        )


