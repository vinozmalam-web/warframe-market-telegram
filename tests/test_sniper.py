from __future__ import annotations

from market_message.models import AuctionAttribute, AuctionItem, SniperRule
from market_message.sniper import format_riven_notification, matches_rule


def test_matches_rule_basic():
    rule = SniperRule(
        name="Rubico CC Rule",
        weapon_url_name="rubico",
        max_price=1000,
        max_rerolls=5,
        seller_status="ingame",
        positive_stats=[{"url_name": "critical_chance", "min_value": 100.0}],
        negative_stat={"mode": "any"},
    )

    matching_auction = AuctionItem(
        id="auc_1",
        weapon_url_name="rubico",
        riven_name="rubico croni-crit",
        attributes=[
            AuctionAttribute("critical_chance", positive=True, value=150.0),
            AuctionAttribute("zoom", positive=False, value=-40.0),
        ],
        buyout_price=500,
        starting_price=400,
        rerolls=2,
        mastery_rank=14,
        polarity="madurai",
        seller_name="Tenno",
        seller_status="ingame",
    )

    assert matches_rule(rule, matching_auction) is True


def test_matches_rule_price_fail():
    rule = SniperRule(max_price=500)
    expensive_auction = AuctionItem(
        id="auc_2",
        weapon_url_name="rubico",
        riven_name="rubico croni-crit",
        attributes=[],
        buyout_price=1200,
        starting_price=1000,
        rerolls=0,
        mastery_rank=10,
        polarity="naramon",
        seller_name="Trader",
        seller_status="ingame",
    )
    assert matches_rule(rule, expensive_auction) is False


def test_matches_rule_negative_stat_none_mode():
    rule = SniperRule(negative_stat={"mode": "none"})
    
    clean_auction = AuctionItem(
        id="auc_3",
        weapon_url_name="gram",
        riven_name="gram crita-tox",
        attributes=[
            AuctionAttribute("critical_chance", positive=True, value=120.0),
        ],
        buyout_price=300,
        starting_price=300,
        rerolls=0,
        mastery_rank=12,
        polarity="vazarin",
        seller_name="Seller",
        seller_status="online",
    )

    neg_auction = AuctionItem(
        id="auc_4",
        weapon_url_name="gram",
        riven_name="gram crita-tox",
        attributes=[
            AuctionAttribute("critical_chance", positive=True, value=120.0),
            AuctionAttribute("status_duration", positive=False, value=-20.0),
        ],
        buyout_price=300,
        starting_price=300,
        rerolls=0,
        mastery_rank=12,
        polarity="vazarin",
        seller_name="Seller",
        seller_status="online",
    )

    assert matches_rule(rule, clean_auction) is True
    assert matches_rule(rule, neg_auction) is False


def test_format_riven_notification():
    rule = SniperRule(name="Rubico CC")
    auction = AuctionItem(
        id="auc_123",
        weapon_url_name="rubico",
        riven_name="rubico croni-crit",
        attributes=[
            AuctionAttribute("critical_chance", positive=True, value=154.2),
            AuctionAttribute("fire_rate", positive=True, value=65.0),
            AuctionAttribute("zoom", positive=False, value=-45.1),
        ],
        buyout_price=1500,
        starting_price=1000,
        rerolls=0,
        mastery_rank=14,
        polarity="madurai",
        seller_name="BestSeller",
        seller_status="ingame",
    )

    html = format_riven_notification(auction, rule, "https://warframe.market")
    assert "Rubico Croni-Crit" in html
    assert "1500 💎" in html
    assert "BestSeller" in html
    assert "/w BestSeller Hi! WTB your [rubico croni-crit] for 1500p" in html


def test_matches_rule_multiple_positive_stats_and_bounds():
    rule = SniperRule(
        name="CC + CD Dual Stat",
        weapon_url_name="rubico",
        positive_stats=[
            {"url_name": "critical_chance", "min_value": 150.0, "max_value": 200.0},
            {"url_name": "critical_damage", "min_value": 120.0},
        ],
    )

    # Fits both CC (150.0 boundary) and CD (130.0)
    auction_pass = AuctionItem(
        id="auc_dual_1",
        weapon_url_name="rubico",
        riven_name="rubico acri-crit",
        attributes=[
            AuctionAttribute("critical_chance", positive=True, value=150.0),
            AuctionAttribute("critical_damage", positive=True, value=130.0),
        ],
        buyout_price=1000,
        starting_price=1000,
        rerolls=0,
        mastery_rank=14,
        polarity="madurai",
        seller_name="Trader",
        seller_status="ingame",
    )

    # Fails because CC exceeds max_value (210 > 200)
    auction_fail_max = AuctionItem(
        id="auc_dual_2",
        weapon_url_name="rubico",
        riven_name="rubico acri-crit",
        attributes=[
            AuctionAttribute("critical_chance", positive=True, value=210.0),
            AuctionAttribute("critical_damage", positive=True, value=130.0),
        ],
        buyout_price=1000,
        starting_price=1000,
        rerolls=0,
        mastery_rank=14,
        polarity="madurai",
        seller_name="Trader",
        seller_status="ingame",
    )

    # Fails because CD is missing
    auction_fail_missing = AuctionItem(
        id="auc_dual_3",
        weapon_url_name="rubico",
        riven_name="rubico croni-crit",
        attributes=[
            AuctionAttribute("critical_chance", positive=True, value=160.0),
            AuctionAttribute("fire_rate", positive=True, value=60.0),
        ],
        buyout_price=1000,
        starting_price=1000,
        rerolls=0,
        mastery_rank=14,
        polarity="madurai",
        seller_name="Trader",
        seller_status="ingame",
    )

    assert matches_rule(rule, auction_pass) is True
    assert matches_rule(rule, auction_fail_max) is False
    assert matches_rule(rule, auction_fail_missing) is False


def test_matches_rule_specific_negative_stat():
    rule = SniperRule(
        negative_stat={
            "mode": "specific",
            "url_name": "zoom",
            "min_value": 30.0,
            "max_value": 60.0,
        }
    )

    auction_matching_zoom = AuctionItem(
        id="auc_zoom_1",
        weapon_url_name="vectis",
        riven_name="vectis croni-crit",
        attributes=[
            AuctionAttribute("critical_chance", positive=True, value=150.0),
            AuctionAttribute("zoom", positive=False, value=-45.0),
        ],
        buyout_price=500,
        starting_price=500,
        rerolls=1,
        mastery_rank=12,
        polarity="naramon",
        seller_name="Sniper",
        seller_status="ingame",
    )

    auction_wrong_negative = AuctionItem(
        id="auc_zoom_2",
        weapon_url_name="vectis",
        riven_name="vectis croni-crit",
        attributes=[
            AuctionAttribute("critical_chance", positive=True, value=150.0),
            AuctionAttribute("recoil", positive=False, value=-30.0),
        ],
        buyout_price=500,
        starting_price=500,
        rerolls=1,
        mastery_rank=12,
        polarity="naramon",
        seller_name="Sniper",
        seller_status="ingame",
    )

    assert matches_rule(rule, auction_matching_zoom) is True
    assert matches_rule(rule, auction_wrong_negative) is False


def test_matches_rule_seller_status_levels():
    rule_ingame = SniperRule(seller_status="ingame")
    rule_online = SniperRule(seller_status="online")

    auc_ingame = AuctionItem(
        id="a1", weapon_url_name="rubico", riven_name="r", attributes=[],
        buyout_price=100, starting_price=100, rerolls=0, mastery_rank=10, polarity="m",
        seller_name="S1", seller_status="ingame"
    )
    auc_online = AuctionItem(
        id="a2", weapon_url_name="rubico", riven_name="r", attributes=[],
        buyout_price=100, starting_price=100, rerolls=0, mastery_rank=10, polarity="m",
        seller_name="S2", seller_status="online"
    )
    auc_offline = AuctionItem(
        id="a3", weapon_url_name="rubico", riven_name="r", attributes=[],
        buyout_price=100, starting_price=100, rerolls=0, mastery_rank=10, polarity="m",
        seller_name="S3", seller_status="offline"
    )

    assert matches_rule(rule_ingame, auc_ingame) is True
    assert matches_rule(rule_ingame, auc_online) is False

    assert matches_rule(rule_online, auc_ingame) is True
    assert matches_rule(rule_online, auc_online) is True
    assert matches_rule(rule_online, auc_offline) is False

