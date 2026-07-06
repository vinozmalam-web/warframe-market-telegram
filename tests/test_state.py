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
