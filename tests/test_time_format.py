from arc_companion.domain.time_format import format_sync_age


def test_none_means_never_synced():
    assert format_sync_age(None) == "Never synced"


def test_zero_seconds():
    assert format_sync_age(0) == "<1 min ago"


def test_just_under_a_minute():
    assert format_sync_age(59) == "<1 min ago"


def test_exactly_one_minute():
    assert format_sync_age(60) == "1 min ago"


def test_several_minutes():
    assert format_sync_age(5 * 60) == "5 mins ago"


def test_just_under_an_hour():
    assert format_sync_age(59 * 60 + 59) == "59 mins ago"


def test_exactly_one_hour():
    assert format_sync_age(3600) == "1 hour ago"


def test_several_hours():
    assert format_sync_age(5 * 3600) == "5 hours ago"


def test_just_under_a_day():
    assert format_sync_age(23 * 3600 + 59 * 60) == "23 hours ago"


def test_exactly_one_day():
    assert format_sync_age(86400) == "1 day ago"


def test_several_days():
    assert format_sync_age(3 * 86400) == "3 days ago"


def test_negative_clamped_to_now():
    # A small clock-skew edge case shouldn't produce a nonsensical string.
    assert format_sync_age(-5) == "<1 min ago"
