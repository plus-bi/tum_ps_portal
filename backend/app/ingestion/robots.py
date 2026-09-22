from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser


class RobotsPolicyUnavailable(RuntimeError): pass
class RobotsDenied(PermissionError): pass


class CachedRobotsPolicy:
    """Fail-closed policy backed by the versioned robots audit cache."""
    def __init__(self, directory: Path | None = None, user_agent: str = "TUM-Project-Studies-Portal"):
        self.directory = directory or Path(__file__).resolve().parents[3] / "compliance/robots"
        self.user_agent = user_agent
        manifest = self.directory / "manifest.json"
        self.records = {row["origin"]: row for row in json.loads(manifest.read_text())["origins"]} if manifest.exists() else {}

    def allowed(self, url: str) -> bool:
        parsed = urlparse(url); origin = f"{parsed.scheme}://{parsed.netloc}"
        record = self.records.get(origin)
        if not record: raise RobotsPolicyUnavailable(f"No cached robots policy for {origin}")
        policy = record["policy"]
        if policy == "allow_all_no_policy": return True
        if policy != "rules_applied": return False
        raw = self.directory / f"{parsed.netloc}.txt"
        parser = RobotFileParser(); parser.set_url(record["robots_url"]); parser.parse(raw.read_text(errors="replace").splitlines())
        return parser.can_fetch(self.user_agent, url)

    def require_allowed(self, url: str) -> None:
        if not self.allowed(url): raise RobotsDenied(f"robots.txt disallows {url}")
