from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class UserState:
    arbg_user_id: str
    steam_id: str | None = None  # populated only if/when the user links Steam
    arbg_friend_user_ids: list[str] = field(default_factory=list)
    # Which friends are currently checked "on" for the grid's friend overlay
    # (see domain/friends.py). Local-only, like arbg_friend_user_ids itself --
    # never included in push_profile's payload.
    arbg_active_friend_ids: list[str] = field(default_factory=list)
    blueprints_owned: list[int] = field(default_factory=list)
    blueprints_wanted: list[int] = field(default_factory=list)
    blueprints_spare: list[int] = field(default_factory=list)
    updated_at: int = 0
    # Epoch seconds of the last successful cloud sync; None means never
    # synced. Distinct from updated_at, which bumps on every local edit.
    last_synced_at: int | None = None
    # The viewer's own resolved Steam display name (Stage D), only when Steam
    # is linked and a Web API key is saved. Local-only, like last_synced_at --
    # never included in push_profile's payload. None falls back to
    # arbg_user_id everywhere this is displayed.
    steam_persona_name: str | None = None
    # Proves ownership of arbg_user_id to the reclaim_profile RPC if this
    # install's supabase_session.json is ever lost but config.json survives
    # (see cloud/sync.py's push_profile_with_recovery). Local-only, like
    # last_synced_at/steam_persona_name -- never included in push_profile's
    # payload; sent only via the dedicated set_recovery_secret/
    # reclaim_profile RPCs, never as a plain table column write.
    recovery_secret: str | None = None


class Store(ABC):
    @abstractmethod
    def load_state(self, user_id: str | None = None) -> UserState:
        """user_id selects whose row to load for a multi-user store (e.g. a
        future cloud store); a single-user local store can ignore it."""
        ...

    @abstractmethod
    def save_state(self, state: UserState) -> None:
        ...
