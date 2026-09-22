import json
from pathlib import Path
import pytest
from app.ingestion.robots import CachedRobotsPolicy, RobotsDenied, RobotsPolicyUnavailable


def policy(tmp_path: Path, status: int, policy_name: str, body: str = "") -> CachedRobotsPolicy:
    origin = "https://example.test"
    (tmp_path / "example.test.txt").write_text(body)
    (tmp_path / "manifest.json").write_text(json.dumps({"origins": [{"origin": origin, "robots_url": origin + "/robots.txt", "status": status, "policy": policy_name}]}))
    return CachedRobotsPolicy(tmp_path)


def test_cached_rules_are_enforced(tmp_path):
    rules = policy(tmp_path, 200, "rules_applied", "User-agent: *\nDisallow: /private\n")
    assert rules.allowed("https://example.test/public")
    with pytest.raises(RobotsDenied): rules.require_allowed("https://example.test/private/file")


def test_404_allows_and_missing_cache_fails_closed(tmp_path):
    assert policy(tmp_path, 404, "allow_all_no_policy").allowed("https://example.test/anything")
    with pytest.raises(RobotsPolicyUnavailable): CachedRobotsPolicy(tmp_path / "missing").allowed("https://example.test/")
