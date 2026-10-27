from __future__ import annotations

from copy import deepcopy


def apply_alignment_reviews(ads: list[dict], ledger: dict) -> list[dict]:
    records = {}
    for review in ledger.get("reviews", []):
        if review["alignment"] not in {"D", "R", "other", "unknown"}:
            raise ValueError(f"Invalid reviewed alignment: {review['id']}")
        if not review["rationale"] or not review["evidence"]:
            raise ValueError(f"Alignment review requires evidence: {review['id']}")
        for record in review["records"]:
            if record["id"] in records:
                raise ValueError(f"Duplicate alignment review: {record['id']}")
            records[record["id"]] = (review, record["source_hash"])

    result = []
    for ad in ads:
        if ad["id"] not in records:
            result.append(ad)
            continue
        review, source_hash = records[ad["id"]]
        if (
            ad["source_hash"] != source_hash
            or ad["source"] != review["source"]
            or ad["sponsor"] != review["sponsor"]
            or ad["alignment"] != review["expected_alignment"]
        ):
            result.append(
                ad
                | {
                    "quality_flags": list(
                        dict.fromkeys(
                            [*ad.get("quality_flags", []), "stale_publisher_alignment_review"]
                        )
                    )
                }
            )
            continue
        evidence = deepcopy({key: value for key, value in review.items() if key != "records"})
        evidence["reviewed_source_hash"] = source_hash
        result.append(
            ad
            | {
                "alignment": review["alignment"],
                "original_alignment": ad["alignment"],
                "alignment_review": evidence,
            }
        )
    return result
