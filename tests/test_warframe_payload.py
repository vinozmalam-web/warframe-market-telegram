from market_message.warframe import extract_chats, extract_messages


def test_extract_chats_accepts_payload_wrapper():
    payload = {
        "payload": {
            "chats": [
                {"id": "chat-1", "unread_count": 2},
                {"chat_id": "chat-2", "unread_messages": 0},
            ]
        }
    }

    chats = extract_chats(payload)

    assert [chat.id for chat in chats] == ["chat-1", "chat-2"]
    assert [chat.unread_count for chat in chats] == [2, 0]


def test_extract_messages_uses_raw_message_when_available_and_sender_names():
    payload = {
        "payload": {
            "messages": [
                {
                    "id": "message-1",
                    "chat_id": "chat-1",
                    "message_from": "user-2",
                    "message": "<p>rendered</p>",
                    "raw_message": "plain",
                    "send_date": "2026-07-05T12:00:00Z",
                }
            ],
            "users": {
                "user-2": {
                    "ingame_name": "Buyer",
                    "slug": "buyer",
                }
            },
        }
    }

    messages = extract_messages(payload, chat_id="chat-1")

    assert len(messages) == 1
    assert messages[0].id == "message-1"
    assert messages[0].chat_id == "chat-1"
    assert messages[0].sender_id == "user-2"
    assert messages[0].sender_name == "Buyer"
    assert messages[0].text == "plain"
