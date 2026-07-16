from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class UserState:
    arbg_user_id: str
    steam_id: str | None = None  # populated only if/when the user links Steam
    arbg_friend_user_ids: list[str] = field(default_factory=list)
    blueprints_owned: list[int] = field(default_factory=list)
    blueprints_wanted: list[int] = field(default_factory=list)
    blueprints_spare: list[int] = field(default_factory=list)
    updated_at: int = 0


class Store(ABC):
    @abstractmethod
    def load_state(self, user_id: str | None = None) -> UserState:
        """user_id selects whose row to load for a multi-user store (e.g. a
        future cloud store); a single-user local store can ignore it."""
        ...

    @abstractmethod
    def save_state(self, state: UserState) -> None:
        ...
