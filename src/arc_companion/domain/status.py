from enum import IntEnum


class BlueprintStatus(IntEnum):
    UNOWNED = 0
    WANT = 1
    OWNED = 2
    HAVE = 3

    def next(self) -> "BlueprintStatus":
        return BlueprintStatus((self.value + 1) % 4)


def status_for(
    blueprint_id: int,
    owned_ids: set[int],
    wanted_ids: set[int],
    spare_ids: set[int],
) -> BlueprintStatus:
    if blueprint_id in spare_ids:
        return BlueprintStatus.HAVE
    if blueprint_id in owned_ids:
        return BlueprintStatus.OWNED
    if blueprint_id in wanted_ids:
        return BlueprintStatus.WANT
    return BlueprintStatus.UNOWNED


def apply_status(
    blueprint_id: int,
    status: BlueprintStatus,
    owned_ids: set[int],
    wanted_ids: set[int],
    spare_ids: set[int],
) -> tuple[set[int], set[int], set[int]]:
    owned_ids = owned_ids - {blueprint_id}
    wanted_ids = wanted_ids - {blueprint_id}
    spare_ids = spare_ids - {blueprint_id}

    if status == BlueprintStatus.OWNED:
        owned_ids = owned_ids | {blueprint_id}
    elif status == BlueprintStatus.WANT:
        wanted_ids = wanted_ids | {blueprint_id}
    elif status == BlueprintStatus.HAVE:
        owned_ids = owned_ids | {blueprint_id}
        spare_ids = spare_ids | {blueprint_id}

    return owned_ids, wanted_ids, spare_ids
