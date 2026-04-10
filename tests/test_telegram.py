from telegram_intel_scraper.providers.telegram import parse_username


def test_parse_username_trims_trailing_slash() -> None:
    assert parse_username("https://t.me/example_channel/") == "example_channel"


def test_parse_username_extracts_final_path_segment() -> None:
    assert parse_username("https://t.me/example_channel") == "example_channel"
