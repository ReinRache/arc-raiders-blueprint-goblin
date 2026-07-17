_MINUTE = 60
_HOUR = 60 * _MINUTE
_DAY = 24 * _HOUR


def _pluralize(count: int, unit: str) -> str:
    return f"{count} {unit}" if count == 1 else f"{count} {unit}s"


def format_sync_age(seconds_ago: int | None) -> str:
    if seconds_ago is None:
        return "Never synced"
    if seconds_ago < 0:
        seconds_ago = 0
    if seconds_ago < _MINUTE:
        return "<1 min ago"
    if seconds_ago < _HOUR:
        return f"{_pluralize(seconds_ago // _MINUTE, 'min')} ago"
    if seconds_ago < _DAY:
        return f"{_pluralize(seconds_ago // _HOUR, 'hour')} ago"
    return f"{_pluralize(seconds_ago // _DAY, 'day')} ago"
