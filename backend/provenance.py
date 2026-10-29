"""Describe stored source evidence without relabeling a fixture as a live offer."""

from datetime import datetime


def source_evidence(listing):
    payload = listing.get("raw_payload")
    raw = payload.get("raw", {}) if isinstance(payload, dict) else {}
    raw = raw if isinstance(raw, dict) else {}
    source = raw.get("data_source", "unverified")
    source = source if isinstance(source, str) else "unverified"
    evidence = raw.get("verification") or {}
    verified = False
    if source == "live" and isinstance(evidence, dict):
        try:
            observed = datetime.fromisoformat(listing["scraped_at"].replace("Z", "+00:00"))
            recorded = datetime.fromisoformat(evidence["observed_at"].replace("Z", "+00:00"))
            verified = (observed.tzinfo is not None and recorded.tzinfo is not None and observed == recorded
                        and evidence.get("status") == "source_validated"
                        and evidence.get("url") == listing["source_url"]
                        and evidence.get("method") in {"json-ld", "html"}
                        and isinstance(evidence.get("run_id"), str) and bool(evidence["run_id"]))
        except (KeyError, ValueError, TypeError, AttributeError):
            pass
    return {"data_source": source if source in {"live", "synthetic"} else "unverified",
            "source_verified": verified, "verification_status": "source_validated" if verified else "synthetic" if source == "synthetic" else "unverified",
            "collection_run_id": evidence.get("run_id") if isinstance(evidence, dict) else None,
            "ai_review_required": isinstance(raw.get("ai_review"), dict) and raw["ai_review"].get("status") != "consistent"}
