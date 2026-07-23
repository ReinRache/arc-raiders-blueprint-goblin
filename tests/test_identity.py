import re

import pytest

from arc_companion.identity import (
    AddFriendError,
    add_friend,
    generate_arbg_id,
    generate_recovery_secret,
    is_valid_arbg_id,
)

_CODE_PATTERN = re.compile(r"^GBLN-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{5}$")
_RECOVERY_SECRET_PATTERN = re.compile(r"^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{32}$")


def test_generate_arbg_id_matches_expected_format():
    for _ in range(200):
        code = generate_arbg_id()
        assert _CODE_PATTERN.match(code), code


def test_generate_arbg_id_is_reasonably_unique():
    codes = {generate_arbg_id() for _ in range(500)}
    # 31^5 possible codes; 500 draws colliding would be statistically absurd
    # unless generation is broken (e.g. always returning the same value).
    assert len(codes) == 500


def test_generate_recovery_secret_matches_expected_format():
    for _ in range(200):
        secret = generate_recovery_secret()
        assert _RECOVERY_SECRET_PATTERN.match(secret), secret


def test_generate_recovery_secret_is_reasonably_unique():
    secrets_generated = {generate_recovery_secret() for _ in range(500)}
    # 32^32 possible secrets; 500 draws colliding would be statistically
    # absurd unless generation is broken.
    assert len(secrets_generated) == 500


def test_is_valid_arbg_id_accepts_well_formed_codes():
    assert is_valid_arbg_id("GBLN-23456")
    assert is_valid_arbg_id("GBLN-ZZZZZ")


def test_is_valid_arbg_id_normalizes_case():
    assert is_valid_arbg_id("gbln-abcde")


def test_is_valid_arbg_id_rejects_malformed_codes():
    assert not is_valid_arbg_id("GBLN-1234")  # too short
    assert not is_valid_arbg_id("GBLN-123456")  # too long
    assert not is_valid_arbg_id("XXXX-23456")  # wrong prefix
    assert not is_valid_arbg_id("GBLN-0O1IL")  # excluded ambiguous characters
    assert not is_valid_arbg_id("not a code at all")
    assert not is_valid_arbg_id("")


def test_add_friend_appends_valid_code():
    result = add_friend("GBLN-23456", own_id="GBLN-99999", current_friends=[])
    assert result == ["GBLN-23456"]


def test_add_friend_normalizes_case():
    result = add_friend("gbln-23456", own_id="GBLN-99999", current_friends=[])
    assert result == ["GBLN-23456"]


def test_add_friend_rejects_invalid_format():
    with pytest.raises(AddFriendError):
        add_friend("not-a-code", own_id="GBLN-99999", current_friends=[])


def test_add_friend_rejects_self_add():
    with pytest.raises(AddFriendError):
        add_friend("GBLN-99999", own_id="GBLN-99999", current_friends=[])


def test_add_friend_rejects_duplicate():
    with pytest.raises(AddFriendError):
        add_friend("GBLN-23456", own_id="GBLN-99999", current_friends=["GBLN-23456"])


def test_add_friend_does_not_mutate_input_list():
    original = ["GBLN-11111"]
    add_friend("GBLN-23456", own_id="GBLN-99999", current_friends=original)
    assert original == ["GBLN-11111"]
