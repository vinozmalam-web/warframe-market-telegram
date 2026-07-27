from market_message.state import StateStore


def test_state_links_telegram_message_to_warframe_chat(tmp_path):
    state = StateStore(tmp_path / "state.sqlite")

    state.link_telegram_message(
        telegram_message_id=9001,
        warframe_message_id="incoming-1",
        chat_id="chat-1",
    )

    assert state.chat_id_for_telegram_message(9001) == "chat-1"
    assert state.chat_id_for_telegram_message(9002) is None


def test_state_stores_telegram_update_offset(tmp_path):
    state = StateStore(tmp_path / "state.sqlite")

    assert state.get_telegram_update_offset() is None

    state.set_telegram_update_offset(43)

    assert state.get_telegram_update_offset() == 43


def test_seen_auctions_price_tracking(tmp_path):
    state = StateStore(tmp_path / "state.sqlite")

    assert state.was_auction_seen("auc_1", price=1000) is False
    assert state.get_seen_auction_price("auc_1") is None

    state.mark_auction_seen("auc_1", price=1000)
    assert state.was_auction_seen("auc_1", price=1000) is True
    assert state.get_seen_auction_price("auc_1") == 1000

    # Price drop/change -> was_auction_seen returns False so it gets re-checked!
    assert state.was_auction_seen("auc_1", price=750) is False

    # Updating seen auction with new price
    state.mark_auction_seen("auc_1", price=750)
    assert state.was_auction_seen("auc_1", price=750) is True
    assert state.get_seen_auction_price("auc_1") == 750


def test_cleanup_old_seen_auctions(tmp_path):
    state = StateStore(tmp_path / "state.sqlite")

    state.mark_auction_seen("auc_recent", price=500)
    state.mark_auction_seen("auc_old", price=1000)

    # Artificially set seen_at timestamp for auc_old to 10 days ago
    with state._connect() as conn:
        conn.execute(
            "UPDATE seen_auctions SET seen_at = datetime('now', '-10 days') WHERE auction_id = ?",
            ("auc_old",),
        )

    deleted = state.cleanup_old_seen_auctions(days=7)
    assert deleted == 1

    assert state.was_auction_seen("auc_recent") is True
    assert state.was_auction_seen("auc_old") is False

