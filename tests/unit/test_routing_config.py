from pathlib import Path

import pytest

from src.services.gateway_service import GatewayConfigurationError, load_routing_config

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_valid_config_builds_exact_match_index() -> None:
    config = load_routing_config(FIXTURES_DIR / "routes_fixture.json")

    index = config.build_index()

    assert index[("GET", "/game")].target_function_name == "tango-music-game-get-game"
    assert (
        index[("POST", "/previews")].target_function_name
        == "tango-music-game-get-previews"
    )
    assert index[("GET", "/leaderboard")].timeout_seconds == 5
    assert ("GET", "/unknown") not in index


def test_new_fixture_entry_is_reachable_without_gateway_code_change() -> None:
    """Adding a routing entry (a config change only) makes a new endpoint reachable (SC-001)."""
    config = load_routing_config(FIXTURES_DIR / "routes_fixture.json")

    index = config.build_index()

    # /broken was added purely as a fixture entry pointing at a non-existent
    # target; no gateway code was written or changed to make it "known" to
    # the routing table.
    assert ("GET", "/broken") in index


def test_duplicate_route_fails_validation() -> None:
    with pytest.raises(GatewayConfigurationError, match="invalid"):
        load_routing_config(FIXTURES_DIR / "routes_fixture_duplicate.json")


def test_empty_entries_fails_validation() -> None:
    with pytest.raises(GatewayConfigurationError, match="invalid"):
        load_routing_config(FIXTURES_DIR / "routes_fixture_empty.json")


def test_malformed_json_fails_validation() -> None:
    with pytest.raises(GatewayConfigurationError, match="not valid JSON"):
        load_routing_config(FIXTURES_DIR / "routes_fixture_malformed.json")


def test_missing_file_fails_validation() -> None:
    with pytest.raises(GatewayConfigurationError, match="not found"):
        load_routing_config(FIXTURES_DIR / "routes_fixture_does_not_exist.json")
