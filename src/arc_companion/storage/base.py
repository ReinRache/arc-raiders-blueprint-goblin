from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class UserState:
    steam_id: str
    blueprints_owned: list[int] = field(default_factory=list)
    blueprints_wanted: list[int] = field(default_factory=list)
    updated_at: int = 0


class Store(ABC):
    @abstractmethod
    def load_state(self, user_id: str) -> UserState:
        ...

    @abstractmethod
    def save_state(self, state: UserState) -> None:
        ...
