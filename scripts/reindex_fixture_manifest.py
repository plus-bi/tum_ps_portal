"""Recalculate the local fixture manifest without performing network requests."""
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.ingestion.adapters import parser_for
from app.ingestion.registry import BY_SLUG

fixtures = ROOT / "backend/tests/fixtures/chairs"
path = fixtures / "manifest.json"
document = json.loads(path.read_text(encoding="utf-8"))
for row in document["sources"]:
    if not row.get("fixture"): continue
    content = (fixtures / row["fixture"]).read_bytes()
    row["sha256"] = hashlib.sha256(content).hexdigest()
    if row["fixture"].endswith(".html"):
        adapter = BY_SLUG[row["slug"]]; parser = parser_for(adapter)
        row["candidates"] = len(parser.discover(adapter, row["final_url"], content))
        row["child_links"] = len(parser.child_links(adapter, row["final_url"], content))
    row.pop("children", None)
document["captured_at"] = datetime.now(timezone.utc).isoformat()
path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
