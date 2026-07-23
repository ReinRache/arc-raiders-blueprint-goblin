"""Local, Steam-independent user identity ("Goblin ID").

Every install gets a short shareable code (GBLN-XXXXX) generated on first
run — no prompt, no external service, no consent needed since it isn't tied
to any real-world identity. Users share this with friends manually instead
of relying on Steam's friend graph; linking a Steam account (steam/) is an
optional add-on, not a requirement.
"""

import random
import secrets

_PREFIX = "GBLN"
_CODE_LENGTH = 5
# Excludes visually-ambiguous characters (0/O, 1/I/L) since these codes get
# read aloud and pasted in chat, not just copy-pasted.
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_RECOVERY_SECRET_LENGTH = 32


def generate_arbg_id() -> str:
    code = "".join(random.choices(_ALPHABET, k=_CODE_LENGTH))
    return f"{_PREFIX}-{code}"


def generate_recovery_secret() -> str:
    """A local-only secret proving ownership of a Goblin ID for the reclaim
    flow (cloud/sync.py's push_profile_with_recovery) -- never displayed or
    shared, unlike generate_arbg_id()'s output. Deliberately uses `secrets`,
    not `random` -- reusing _ALPHABET is fine (it's just a safe character
    set), but reusing `random`'s non-cryptographic Mersenne Twister here
    would undermine the entire recovery-secret security model, which
    depends on this being genuinely unguessable."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(_RECOVERY_SECRET_LENGTH))


def is_valid_arbg_id(code: str) -> bool:
    code = code.strip().upper()
    if not code.startswith(f"{_PREFIX}-"):
        return False
    suffix = code[len(_PREFIX) + 1 :]
    return len(suffix) == _CODE_LENGTH and all(c in _ALPHABET for c in suffix)


class AddFriendError(ValueError):
    pass


def add_friend(friend_id: str, own_id: str, current_friends: list[str]) -> list[str]:
    """Pure function: returns the updated friends list, or raises
    AddFriendError with a user-facing message. Never mutates current_friends."""
    friend_id = friend_id.strip().upper()
    if not is_valid_arbg_id(friend_id):
        raise AddFriendError(f'"{friend_id}" doesn\'t look like a valid Goblin ID (expected {_PREFIX}-XXXXX).')
    if friend_id == own_id.strip().upper():
        raise AddFriendError("You can't add your own Goblin ID as a friend.")
    if friend_id in current_friends:
        raise AddFriendError(f"{friend_id} is already in your friends list.")
    return [*current_friends, friend_id]
