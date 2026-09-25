"""Run and score project-profile extractions over the labeled evaluation set.

    python scripts/eval_project_profiles.py run --effort low --out /tmp/profile_eval/low
    python scripts/eval_project_profiles.py run --variant one-list --out /tmp/profile_eval/one_list
    python scripts/eval_project_profiles.py score /tmp/profile_eval/low /tmp/profile_eval/medium
    python scripts/eval_project_profiles.py score --recheck /tmp/profile_eval/low   # after a checker change

`run` calls Azure OpenAI once or twice per document and loads real pages from the compose
Postgres. Existing outputs are skipped, so an interrupted run can resume. Outputs contain
extracted document facts: keep them outside the repository. `score` makes no model calls.
See docs/pdf-project-profile-v3-plan.md §8.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT)  # settings() reads .env relative to the working directory

from pydantic import BaseModel, create_model  # noqa: E402

from app.config import settings  # noqa: E402
from app.ingestion import llm_client, profile_eval  # noqa: E402
from app.ingestion.pdf_reader import render_for_llm  # noqa: E402
from app.ingestion.profile_evidence import check_profile_evidence  # noqa: E402
from app.ingestion.project_profile import (SCHEMA_VERSION, DocumentExtraction, ListField, PdfTextCoverage,  # noqa: E402
                                           ProfileExtraction, ProjectProfile)


class Prerequisite(BaseModel):
    skill: str
    strength: Literal["required", "recommended"]


def _one_list_fields() -> dict:
    fields = {}
    for name, info in ProjectProfile.model_fields.items():
        if name == "prerequisites_required":
            fields["prerequisites"] = (ListField[Prerequisite], ...)
        elif name != "prerequisites_recommended":
            fields[name] = (info.annotation, info)
    return fields


OneListOffer = create_model("OneListOffer", **_one_list_fields())


class OneListDocument(DocumentExtraction):
    offers: list[OneListOffer]  # type: ignore[valid-type]


TWO_LIST_RULE = "Keep mandatory skills separate from recommendations,"
ONE_LIST_RULE = ("Give each prerequisite a strength: recommended only when it is called desirable, preferred, a plus "
                 "or optional, otherwise required,")
assert TWO_LIST_RULE in llm_client.SYSTEM_PROMPT
ONE_LIST_PROMPT = llm_client.SYSTEM_PROMPT.replace(TWO_LIST_RULE, ONE_LIST_RULE)


def _to_two_lists(doc: OneListDocument) -> DocumentExtraction:
    """Maps the variant back to the production schema so both variants are scored identically."""
    offers = []
    for offer in doc.offers:
        values = offer.model_dump()
        items = values.pop("prerequisites")["items"]
        for strength in ("required", "recommended"):
            chosen = [{"value": item["value"]["skill"], "evidence": item["evidence"]}
                      for item in items if item["value"]["strength"] == strength]
            values[f"prerequisites_{strength}"] = {"stated": bool(chosen), "items": chosen}
        offers.append(values)
    return DocumentExtraction.model_validate({**doc.model_dump(exclude={"offers"}), "offers": offers})


def load_pages(content_hash: str, label: dict) -> tuple[list[str], str, str]:
    if "pages" in label:
        return label["pages"], "digital_native", "synthetic"
    query = ("select json_build_object('pages', extracted_markdown_pages, 'classification', classification, "
             f"'classifier_version', classifier_version) from pdf_analysis where content_hash = '{content_hash}'")
    output = subprocess.run(["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "portal", "-d", "portal",
                             "-A", "-t", "-c", query], check=True, capture_output=True, text=True, cwd=ROOT).stdout
    if not output.strip():
        raise SystemExit(f"No pdf_analysis row for {content_hash}")
    row = json.loads(output)
    return row["pages"], row["classification"], row["classifier_version"]


def extract_one_list(content_hash: str, pages: list[str], classification: str, classifier_version: str,
                     effort: str) -> ProfileExtraction:
    metadata = dict(content_hash=content_hash, schema_version=SCHEMA_VERSION + "+one-list",
                    prompt_version="one-list", prompt_hash=hashlib.sha256(ONE_LIST_PROMPT.encode()).hexdigest(),
                    model_deployment=settings().azure_openai_deployment, reasoning_effort=effort,
                    coverage=PdfTextCoverage.from_pages(classification, classifier_version, pages))
    try:
        outcome = llm_client.extract_project_profile(render_for_llm(pages), system_prompt=ONE_LIST_PROMPT,
                                                     reasoning_effort=effort, text_format=OneListDocument)
    except llm_client.ProfileExtractionError as error:
        return ProfileExtraction(**metadata, status="failed", attempts=error.attempts, errors=error.errors,
                                 **vars(error.usage))
    document = _to_two_lists(outcome.document)
    return ProfileExtraction(**metadata, status="ok", attempts=outcome.attempts, document=document,
                             evidence_issues=check_profile_evidence(document, pages), **vars(outcome.usage))


def _file_name(content_hash: str) -> str:
    return content_hash.replace(":", "_") + ".json"


def run(args) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for content_hash, label in profile_eval.load_labels().items():
        if args.only and not any(content_hash.startswith(prefix) for prefix in args.only):
            continue
        path = out / _file_name(content_hash)
        if path.exists():
            continue
        pages, classification, classifier_version = load_pages(content_hash, label)
        started = time.monotonic()
        if args.variant == "one-list":
            result = extract_one_list(content_hash, pages, classification, classifier_version, args.effort)
        else:
            result = llm_client.extract_project_profile_result_for_pages(
                content_hash, pages, classification, classifier_version, reasoning_effort=args.effort)
        latency = round(time.monotonic() - started, 1)
        path.write_text(json.dumps({"latency_seconds": latency, "result": result.model_dump(mode="json")}, indent=1))
        print(f"{content_hash[:12]} {result.status} attempts={result.attempts} {latency}s "
              f"out={result.output_tokens} issues={len(result.evidence_issues)}")


def score_dir(directory: Path, labels: dict, recheck: bool = False) -> tuple[dict, dict]:
    """recheck re-runs the citation checker on stored outputs, so checker fixes need no new model calls."""
    scores, latency = {}, {}
    for content_hash, label in labels.items():
        path = directory / _file_name(content_hash)
        if path.exists():
            stored = json.loads(path.read_text())
            result = ProfileExtraction.model_validate(stored["result"])
            if recheck and result.document is not None:
                result.evidence_issues = check_profile_evidence(result.document, load_pages(content_hash, label)[0])
            scores[content_hash] = profile_eval.score_document(label, result)
            latency[content_hash] = stored["latency_seconds"]
    summary = profile_eval.summarize(scores)
    summary["latency_seconds"] = round(sum(latency.values()), 1)
    return summary, scores


def score(args) -> None:
    labels = profile_eval.load_labels()
    runs = {directory: score_dir(Path(directory), labels, args.recheck) for directory in args.dirs}
    if len(runs) == 2:  # paired: compare only documents present in both runs
        (first, (_, a)), (second, (_, b)) = runs.items()
        shared = set(a) & set(b)
        runs = {first: (profile_eval.summarize({h: a[h] for h in shared}), a),
                second: (profile_eval.summarize({h: b[h] for h in shared}), b)}
    for directory, (summary, scores) in runs.items():
        print(f"== {directory}")
        print(json.dumps({key: value for key, value in summary.items() if key != "checks"}))
        for key, (mean, count) in summary["checks"].items():
            print(f"  {key:28} {mean:6.3f}  n={count}")
        if args.verbose:
            for content_hash, doc in scores.items():
                failed = sorted({key for offer in doc["offers"] for key, value in offer.items()
                                 if value is False or (isinstance(value, float) and value < 1)}
                                | {key for key, value in doc["checks"].items() if value is not True and value != 1})
                print(f"  {content_hash[:12]} {doc['status']} {failed}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--effort", choices=["low", "medium", "high"], default="low")
    run_parser.add_argument("--variant", choices=["production", "one-list"], default="production")
    run_parser.add_argument("--out", required=True)
    run_parser.add_argument("--only", nargs="*", help="content-hash prefixes")
    score_parser = commands.add_parser("score")
    score_parser.add_argument("dirs", nargs="+")
    score_parser.add_argument("-v", "--verbose", action="store_true")
    score_parser.add_argument("--recheck", action="store_true", help="re-run the citation checker (reads pages)")
    args = parser.parse_args()
    run(args) if args.command == "run" else score(args)


if __name__ == "__main__":
    main()
