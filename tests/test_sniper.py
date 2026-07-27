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


def test_broad_rule_notification_cap(tmp_path):
    from market_message.sniper import RivenSniperEngine
    from market_message.state import StateStore

    sent_messages = []

    class FakeTelegram:
        def send_message(self, text, parse_mode=None, reply_markup=None):
            sent_messages.append(text)
            return True

    class FakeWarframe:
        def search_auctions(self, type_="riven", weapon_url_name=None):
            return [
                AuctionItem(
                    id=f"auc_{i}",
                    weapon_url_name="rubico",
                    riven_name=f"rubico_{i}",
                    attributes=[],
                    buyout_price=100 + i,
                    starting_price=100 + i,
                    rerolls=0,
                    mastery_rank=10,
                    polarity="madurai",
                    seller_name=f"Seller{i}",
                    seller_status="ingame",
                )
                for i in range(10)
            ]

    state = StateStore(tmp_path / "test_state.sqlite")
    rule = SniperRule(name="Broad Rubico Rule", weapon_url_name="rubico", is_active=True)
    state.create_sniper_rule(rule)

    engine = RivenSniperEngine(
        warframe=FakeWarframe(),
        telegram=FakeTelegram(),
        state=state,
        market_base_url="https://warframe.market",
        max_alerts_per_rule_run=3,
    )

    notified = engine.check_auctions_once()

    # 3 auction notifications sent out of 10 matches
    assert notified == 3
    # Total sent telegram messages = 3 alerts + 1 summary message
    assert len(sent_messages) == 4
    assert "Сработало широкое правило" in sent_messages[-1]
    assert "Найдено совпадений: <b>10</b>" in sent_messages[-1]

    # Check that all 10 auctions were marked as seen in state store
    for i in range(10):
        assert state.was_auction_seen(f"auc_{i}") is True

    # Second check run should find 0 new items
    sent_messages.clear()
    second_notified = engine.check_auctions_once()
    assert second_notified == 0
    assert len(sent_messages) == 0


def test_sniper_price_drop_retrigger(tmp_path):
    from market_message.sniper import RivenSniperEngine
    from market_message.state import StateStore

    sent_messages = []

    class FakeTelegram:
        def send_message(self, text, parse_mode=None, reply_markup=None):
            sent_messages.append(text)
            return True

    class DynamicWarframe:
        def __init__(self):
            self.price = 1000

        def search_auctions(self, type_="riven", weapon_url_name=None):
            return [
                AuctionItem(
                    id="auc_pd_1",
                    weapon_url_name="vectis",
                    riven_name="vectis croni-crit",
                    attributes=[],
                    buyout_price=self.price,
                    starting_price=self.price,
                    rerolls=0,
                    mastery_rank=12,
                    polarity="madurai",
                    seller_name="Seller1",
                    seller_status="ingame",
                )
            ]

    state = StateStore(tmp_path / "test_state.sqlite")
    rule = SniperRule(name="Vectis Rule", weapon_url_name="vectis", max_price=1200, is_active=True)
    state.create_sniper_rule(rule)

    wf_client = DynamicWarframe()
    engine = RivenSniperEngine(
        warframe=wf_client,
        telegram=FakeTelegram(),
        state=state,
        market_base_url="https://warframe.market",
    )

    # First check run at 1000p
    notified_1 = engine.check_auctions_once()
    assert notified_1 == 1
    assert "1000 💎" in sent_messages[0]
    assert "Снижение цены" not in sent_messages[0]

    # Second check run at same 1000p -> 0 alerts sent
    sent_messages.clear()
    notified_2 = engine.check_auctions_once()
    assert notified_2 == 0

    # Third check run: Seller lowers price to 450p -> Alert RETRIGGERED with price drop badge!
    sent_messages.clear()
    wf_client.price = 450
    notified_3 = engine.check_auctions_once()
    assert notified_3 == 1
    assert "Снижение цены на Riven" in sent_messages[0]
    assert "450 💎" in sent_messages[0]
    assert "было 1000 💎" in sent_messages[0]
    assert state.get_seen_auction_price("auc_pd_1") == 450


def test_sniper_wildcard_weapon_disabled(tmp_path):
    from market_message.sniper import RivenSniperEngine
    from market_message.state import StateStore

    calls = []

    class FakeTelegram:
        def send_message(self, text, parse_mode=None, reply_markup=None):
            return True

    class FakeWarframe:
        def search_auctions(self, type_="riven", weapon_url_name=None, positive_stats=None, sort_by=None):
            calls.append(weapon_url_name)
            return []

    state = StateStore(tmp_path / "test_state.sqlite")
    rule = SniperRule(
        name="Wildcard Rule",
        weapon_url_name="*",
        max_price=500,
        is_active=True,
    )
    state.create_sniper_rule(rule)

    engine = RivenSniperEngine(
        warframe=FakeWarframe(),
        telegram=FakeTelegram(),
        state=state,
        market_base_url="https://warframe.market",
    )

    notified = engine.check_auctions_once()
    # Wildcard search is disabled, so zero alerts and zero API calls should occur
    assert notified == 0
    assert len(calls) == 0





