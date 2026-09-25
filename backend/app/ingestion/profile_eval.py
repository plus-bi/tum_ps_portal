"""Deterministic scoring of project-profile extractions against hand labels.

Labels live in ../../tests/fixtures/profile_eval/labels.json (format described there). Scoring is
pure: it takes stored ProfileExtraction results and never calls the model, so a run can be
re-scored after reviewers change the labels. See ../../../docs/pdf-project-profile-v3-plan.md §8.
"""
from __future__ import annotations

import json
from enum import Enum
from collections import Counter
from pathlib import Path

from .project_profile import Contact, ListField, ProfileExtraction, ProjectProfile, TextField

LABELS_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "profile_eval" / "labels.json"

# label key -> how the offer value is read for exact (categorical/set) comparison
ASSESSMENT_LABELS = {
    "programming_performed": lambda offer: offer.programming_performed.level,
    "programming_required": lambda offer: offer.programming_required.level,
    "work_location_mode": lambda offer: offer.work_location_mode.level,
    "start_date_normalized": lambda offer: offer.start_date.normalized,
}
SET_LABELS = {
    "project_types": lambda offer: _values(offer.project_types),
    "degree_level": lambda offer: _values(offer.degree_level),
}


def load_labels(path: Path = LABELS_PATH) -> dict[str, dict]:
    return json.loads(path.read_text())["documents"]


def _values(field: ListField) -> list[str]:
    values = []
    for item in field.items:
        if isinstance(item.value, Contact):
            values.append(" ".join(part for part in (item.value.name, item.value.email) if part))
        else:
            values.append(item.value.value if isinstance(item.value, Enum) else str(item.value))
    return values


def _emails(offer: ProjectProfile) -> str:
    return " ".join((item.value.email or "").lower() for item in offer.contacts.items)


def _lower(field: TextField) -> str:
    return (field.value or "").lower() if field.stated else ""


def _offer_text(offer: ProjectProfile) -> str:
    """Every extracted value of an offer, lowercased, for leakage checks. Excludes the summary,
    which restates the same facts."""
    parts = []
    for name in ProjectProfile.model_fields:
        field = getattr(offer, name)
        if isinstance(field, TextField):
            parts.append(_lower(field))
        elif isinstance(field, ListField):
            parts.extend(value.lower() for value in _values(field))
    return "\n".join(parts)


def _match_score(label: dict, offer: ProjectProfile) -> float:
    labeled, predicted = set(label["source_pages"]), set(offer.source_pages)
    score = len(labeled & predicted) / len(labeled | predicted)
    title = _lower(offer.title)
    if any(key in title for key in label.get("title_keys", [])):
        score += 1
    email = _emails(offer)
    if any(key in email for key in label.get("contact_emails", [])):
        score += 0.5
    return score


def match_offers(labels: list[dict], offers: list[ProjectProfile]) -> list[tuple[int, int]]:
    """Greedy one-to-one matching by page overlap, title and contact; pairs with no page overlap
    and no title/contact match are left unmatched."""
    candidates = sorted(((_match_score(label, offer), li, oi) for li, label in enumerate(labels)
                         for oi, offer in enumerate(offers)), reverse=True)
    pairs, used_labels, used_offers = [], set(), set()
    for score, li, oi in candidates:
        if score > 0 and li not in used_labels and oi not in used_offers:
            pairs.append((li, oi))
            used_labels.add(li)
            used_offers.add(oi)
    return sorted(pairs)


def score_offer(label: dict, offer: ProjectProfile) -> dict[str, float | bool]:
    """Checks only the fields the label specifies. Booleans are pass/fail; floats are recalls."""
    checks: dict[str, float | bool] = {"boundary_exact": set(label["source_pages"]) == set(offer.source_pages)}
    if label.get("title_keys"):
        checks["title"] = any(key in _lower(offer.title) for key in label["title_keys"])
    if "contact_emails" in label:
        email = _emails(offer)
        checks["contact"] = (any(key in email for key in label["contact_emails"]) if label["contact_emails"]
                             else not email.strip())
        if len(label["contact_emails"]) > 1:
            checks["contacts_complete"] = all(key in email for key in label["contact_emails"])
    for key, read in ASSESSMENT_LABELS.items():
        if key in label:
            checks[key] = read(offer) in label[key]
    for key, read in SET_LABELS.items():
        if key in label:
            checks[key] = set(read(offer)) in [set(values) for values in label[key]]
    if "working_language" in label:
        languages = [value.lower() for value in _values(offer.working_language)]
        checks["working_language"] = (any(key in value for key in label["working_language"] for value in languages)
                                      if label["working_language"] else not offer.working_language.stated)

    modes = set(_values(offer.work_modes))
    if label.get("work_modes_required"):
        checks["work_modes_recall"] = len(modes & set(label["work_modes_required"])) / len(label["work_modes_required"])
    if label.get("work_modes_forbidden"):
        checks["work_modes_no_forbidden"] = not modes & set(label["work_modes_forbidden"])

    if label.get("prerequisites"):
        required = [value.lower() for value in _values(offer.prerequisites_required)]
        recommended = [value.lower() for value in _values(offer.prerequisites_recommended)]
        found = strength_ok = 0
        for prerequisite in label["prerequisites"]:
            in_required = any(prerequisite["key"] in value for value in required)
            in_recommended = any(prerequisite["key"] in value for value in recommended)
            found += in_required or in_recommended
            strength_ok += in_required if prerequisite["strength"] == "required" else in_recommended
        checks["prerequisite_recall"] = found / len(label["prerequisites"])
        checks["prerequisite_strength"] = strength_ok / len(label["prerequisites"])

    if "deliverables_required" in label:
        deliverables = [value.lower() for value in _values(offer.deliverables)]
        groups = label["deliverables_required"]
        allowed = label.get("deliverable_keys", []) + [key for group in groups for key in group]
        checks["deliverables_supported"] = all(any(key in value for key in allowed) for value in deliverables)
        if groups:
            checks["deliverable_recall"] = sum(
                any(key in value for key in group for value in deliverables) for group in groups) / len(groups)
    if label.get("forbidden_keys"):
        text = _offer_text(offer)
        checks["no_leakage"] = not any(key in text for key in label["forbidden_keys"])
    return checks


def score_document(label: dict, result: ProfileExtraction) -> dict:
    offer_labels = [{**label.get("offer_defaults", {}), **offer} for offer in label["offers"]]
    scored = {
        "status": result.status,
        "attempts": result.attempts,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "reasoning_tokens": result.reasoning_tokens,
        "evidence_issues": dict(Counter(issue.reason for issue in result.evidence_issues)),
        "checks": {},
        "offers": [],
    }
    if result.document is None:
        return scored
    offers = result.document.offers
    pairs = match_offers(offer_labels, offers)
    scored["checks"] = {
        "document_kind": result.document.document_kind in label["document_kind"],
        "offer_count": len(offers) == len(offer_labels),
        "offer_recall": len(pairs) / len(offer_labels) if offer_labels else float(not offers),
    }
    scored["offers"] = [{"label_index": li, "offer_index": oi, **score_offer(offer_labels[li], offers[oi])}
                        for li, oi in pairs]
    scored["unmatched_offers"] = len(offers) - len(pairs)
    return scored


def summarize(scores: dict[str, dict]) -> dict:
    """Mean of every check over documents and matched offers, plus totals."""
    values: dict[str, list[float]] = {}
    for doc in scores.values():
        for key, value in doc["checks"].items():
            values.setdefault(key, []).append(float(value))
        for offer in doc["offers"]:
            for key, value in offer.items():
                if key not in ("label_index", "offer_index"):
                    values.setdefault(key, []).append(float(value))
    issues = Counter()
    for doc in scores.values():
        issues.update(doc["evidence_issues"])
    return {
        "documents": len(scores),
        "failed": sum(doc["status"] == "failed" for doc in scores.values()),
        "retried": sum(doc["attempts"] > 1 for doc in scores.values()),
        "input_tokens": sum(doc["input_tokens"] for doc in scores.values()),
        "output_tokens": sum(doc["output_tokens"] for doc in scores.values()),
        "reasoning_tokens": sum(doc["reasoning_tokens"] for doc in scores.values()),
        "evidence_issues": dict(issues),
        "checks": {key: (round(sum(v) / len(v), 3), len(v)) for key, v in sorted(values.items())},
    }
