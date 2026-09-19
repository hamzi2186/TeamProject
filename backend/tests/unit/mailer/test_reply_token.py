from uuid import uuid4

import pytest

from app.modules.mailer.thread import (
    build_reply_to_address,
    extract_reply_to_token,
    make_reply_to_token,
    resolve_reply_to_token,
)

SECRET = "test-signing-secret"


def test_token_round_trips_to_the_conversation_id():
    conversation_id = uuid4()
    token = make_reply_to_token(conversation_id, SECRET)
    assert resolve_reply_to_token(token, SECRET) == conversation_id


def test_each_conversation_gets_its_own_token():
    assert make_reply_to_token(uuid4(), SECRET) != make_reply_to_token(uuid4(), SECRET)


def test_token_survives_a_mail_server_changing_its_case():
    conversation_id = uuid4()
    token = make_reply_to_token(conversation_id, SECRET)
    assert resolve_reply_to_token(token.upper(), SECRET) == conversation_id


def test_token_does_not_contain_the_secret():
    assert SECRET not in make_reply_to_token(uuid4(), SECRET)


@pytest.mark.parametrize("tamper", ["id", "signature", "secret"])
def test_forged_tokens_are_rejected(tamper):
    conversation_id = uuid4()
    token = make_reply_to_token(conversation_id, SECRET)
    key, signature = token.split("-")
    if tamper == "id":
        # Point a valid signature at someone else's conversation.
        assert resolve_reply_to_token(f"{uuid4().hex}-{signature}", SECRET) is None
    elif tamper == "signature":
        flipped = ("0" if signature[0] != "0" else "1") + signature[1:]
        assert resolve_reply_to_token(f"{key}-{flipped}", SECRET) is None
    else:
        assert resolve_reply_to_token(token, "another-secret") is None


@pytest.mark.parametrize(
    "token", [None, "", "   ", "not-a-token", "abc", f"{'z' * 32}-{'0' * 16}", f"{uuid4().hex}"]
)
def test_malformed_tokens_resolve_to_nothing(token):
    assert resolve_reply_to_token(token, SECRET) is None


def test_a_missing_secret_can_neither_mint_nor_verify():
    conversation_id = uuid4()
    with pytest.raises(ValueError):
        make_reply_to_token(conversation_id, "")
    assert resolve_reply_to_token(make_reply_to_token(conversation_id, SECRET), "") is None


def test_token_survives_being_put_in_a_reply_to_address_and_read_back():
    conversation_id = uuid4()
    token = make_reply_to_token(conversation_id, SECRET)
    address = build_reply_to_address(mailbox="mailer", domain="reply.example.com", token=token)
    assert address == f"mailer+{token}@reply.example.com"
    assert extract_reply_to_token(address) == token
    assert resolve_reply_to_token(extract_reply_to_token(address), SECRET) == conversation_id
