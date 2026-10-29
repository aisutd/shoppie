"""Compare eligible observations before testing whether their variants agree."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from db.similarity import assess_identity


def rank_deals(results, store, now=None, max_age_hours=48, require_verified=False):
    now = now or datetime.now(timezone.utc)
    eligible, offers, excluded = [], [], []
    for result in results:
        row, reason = dict(result), None
        if require_verified and (row.get("data_source") != "live" or not row.get("source_verified")):
            reason = "live source evidence has not been verified"
        elif row["match_status"] != "exact":
            reason = "incomplete identity evidence needs manual review"
        elif row.get("availability") != "in_stock":
            reason = "not explicitly in stock"
        elif row.get("price") is None or row.get("currency") != "USD":
            reason = "no comparable USD price"
        else:
            try:
                observed = datetime.fromisoformat(row["scraped_at"].replace("Z", "+00:00"))
                age = now - observed
                if age < -timedelta(minutes=5) or age > timedelta(hours=max_age_hours):
                    reason = "observation is stale or dated in the future"
            except (ValueError, TypeError, KeyError):
                reason = "observation time is invalid"
        if reason:
            excluded.append({"id": row["id"], "reason": reason})
        else:
            eligible.append(row)
    # unavailable, stale, and unverified rows cannot poison valid comparisons
    ambiguous = set()
    for index, left in enumerate(eligible):
        for right in eligible[index+1:]:
            conditions_differ = left.get("condition") != right.get("condition")
            if conditions_differ or assess_identity(left, right)["status"] == "rejected":
                ambiguous.update((left["id"], right["id"]))
    for row in eligible:
        if row["id"] in ambiguous:
            excluded.append({"id": row["id"], "reason": "different models, variants, or conditions fit this request; refine it before comparing prices"})
            continue
        price = Decimal(str(row["price"]))
        shipping = Decimal(str(row["shipping_cost"])) if row.get("shipping_cost") is not None else None
        total = price + shipping if shipping is not None else None
        row["total_price"] = str(total) if total is not None else None
        row["deal_reasons"] = ["exact requested configuration", "explicitly in stock", f"fresh within {max_age_hours} hours"]
        row["deal_reasons"].append("shipping included in known total" if shipping is not None else "shipping unknown; subtotal cannot establish the lowest total")
        history = store.history(row["id"])
        previous = [item for item in history if item["scraped_at"] < row["scraped_at"] and item.get("price") is not None and item.get("currency") == "USD"]
        if previous:
            row["deal_reasons"].append(f"previous observed listing price: USD {previous[-1]['price']}")
        row["recommended"] = False
        offers.append(row)
    offers.sort(key=lambda row: (row["total_price"] is None,
                                Decimal(row["total_price"] or str(row["price"])), row["retailer_key"]))
    known = [row for row in offers if row["total_price"] is not None]
    if known:
        lowest = Decimal(known[0]["total_price"])
        for row in known:
            if Decimal(row["total_price"]) == lowest:
                row["recommended"] = True
                row["deal_reasons"].append("lowest known total among retrieved fresh exact offers with known shipping")
    return {"offers": offers, "excluded": excluded,
            "retailers": len({row["retailer_key"] for row in offers}),
            "comparison_basis": "known USD totals; unknown shipping shown separately"}
