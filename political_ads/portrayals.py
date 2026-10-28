from __future__ import annotations

from collections import Counter

from political_ads.analysis import publisher, unique_messages
from political_ads.schema import digest

PARTIES = ("D", "R")
TONES = ("negative_only", "positive_only", "mixed", "neutral_only")
VOICES = ("advertiser", "adopted_clip")
SCOPES = ("opponents", "self", "same_party_opponents", "collective_opponents")


def validate_description(description: dict, text: str, codebook: dict) -> None:
    allowed = {
        "target_party": ("D", "R", "other", "unknown"),
        "target_kind": ("person", "collective"),
        "target_role": ("self_or_supported", "opponent", "unclear"),
        "party_basis": ("candidate_metadata", "explicit_text", "national_crosswalk", "unknown"),
        "frame": codebook["frames"],
        "tone": ("negative", "positive", "neutral"),
        "voice": codebook["voices"],
    }
    if not description.get("target", "").strip():
        raise ValueError("Portrayal requires an actual target")
    for key, values in allowed.items():
        if description.get(key) not in values:
            raise ValueError(f"Invalid portrayal {key}: {description.get(key)}")
    if description["target_party"] != "unknown" and description["party_basis"] == "unknown":
        raise ValueError("Portrayal party requires an identity basis")
    quote, phrase, anchor = (
        description.get(key, "") for key in ("quote", "phrase", "target_quote")
    )
    if not quote or not phrase or not anchor or quote not in text or anchor not in text:
        raise ValueError("Portrayal quote or target anchor is not literal source text")
    if phrase not in quote:
        raise ValueError("Portrayal phrase is not within its quoted evidence")
    for key, value in (("", quote), ("target_", anchor)):
        if key + "start" in description or key + "end" in description:
            if text[description[key + "start"] : description[key + "end"]] != value:
                raise ValueError("Broken portrayal evidence offsets")


def evidence_spans(description: dict, text: str, codebook: dict) -> dict:
    validate_description(description, text, codebook)
    quote_start = description.get("start", text.index(description["quote"]))
    target_start = description.get("target_start", text.index(description["target_quote"]))
    return description | {
        "start": quote_start,
        "end": quote_start + len(description["quote"]),
        "target_start": target_start,
        "target_end": target_start + len(description["target_quote"]),
    }


def bind_reviews(
    inputs: list[dict], decisions: list[dict], codebook: dict, *, snapshot_id: str
) -> dict:
    by_id = {ad["id"]: ad for ad in inputs}
    if len(by_id) != len(inputs):
        raise ValueError("Duplicate portrayal review input identity")
    seen = set()
    reviews = []
    for decision in decisions:
        identity = decision["ad_id"]
        if identity in seen or identity not in by_id:
            raise ValueError(f"Duplicate or unexpected portrayal decision: {identity}")
        seen.add(identity)
        ad = by_id[identity]
        if ad["text_hash"] != digest(ad["text"]):
            raise ValueError(f"Frozen portrayal input hash mismatch: {identity}")
        if (
            decision.get("status") not in ("reviewed", "uncertain")
            or not isinstance(decision.get("descriptions"), list)
            or not isinstance(decision.get("reason"), str)
            or (
                (decision["status"] == "uncertain" or not decision["descriptions"])
                and not decision["reason"].strip()
            )
        ):
            raise ValueError(f"Invalid portrayal review outcome: {identity}")
        reviews.append(
            decision
            | {
                key: ad[key]
                for key in (
                    "alignment",
                    "sponsor",
                    "source",
                    "source_hash",
                    "text_hash",
                    "message_id",
                )
            }
            | {
                "descriptions": [
                    evidence_spans(d, ad["text"], codebook) for d in decision["descriptions"]
                ]
            }
        )
    if seen != set(by_id):
        raise ValueError(f"Incomplete portrayal review: {len(seen)}/{len(by_id)} decisions")
    return {
        "version": codebook["version"],
        "method": codebook["method"],
        "input_snapshot_id": snapshot_id,
        "input_messages": len(inputs),
        "independent_human_gold": False,
        "reviews": sorted(reviews, key=lambda review: review["ad_id"]),
    }


def review_key(ad: dict) -> tuple:
    # Identical words from a different sponsor can have a different first-person target.
    return ad["alignment"], ad["sponsor"], ad["text_hash"]


def apply_portrayal_reviews(ads: list[dict], ledger: dict, codebook: dict) -> list[dict]:
    if ledger and ledger.get("version") != codebook.get("version"):
        raise ValueError("Portrayal review and codebook versions disagree")
    by_id, by_text = {}, {}
    for review in ledger.get("reviews", []):
        if review["ad_id"] in by_id:
            raise ValueError(f"Duplicate portrayal review: {review['ad_id']}")
        if review.get("status") not in ("reviewed", "uncertain"):
            raise ValueError("Invalid saved portrayal review status")
        if (review["status"] == "uncertain" or not review["descriptions"]) and not review.get(
            "reason"
        ):
            raise ValueError("Uncertain or no-description review requires a reason")
        by_id[review["ad_id"]] = review
        key = review_key(review)
        if key in by_text and any(
            by_text[key][field] != review[field] for field in ("status", "reason", "descriptions")
        ):
            raise ValueError("Conflicting portrayal reviews of identical sponsor/text")
        by_text[key] = review
    result = []
    for ad in ads:
        review = by_id.get(ad["id"]) or by_text.get(review_key(ad))
        attached = {
            "status": "unreviewed",
            "reason": "Not yet context-reviewed",
            "descriptions": [],
        }
        if review:
            if review_key(ad) != review_key(review):
                attached = {
                    "status": "stale",
                    "reason": "Text, sponsor or alignment changed; a new review is required",
                    "descriptions": [],
                    "previous_review": review,
                }
            else:
                if digest(ad["text"]) != review["text_hash"]:
                    raise ValueError("Portrayal review text hash mismatch")
                attached = review | {
                    "descriptions": [
                        evidence_spans(d, ad["text"], codebook) for d in review["descriptions"]
                    ],
                    "source_hash_changed": review["source_hash"] != ad["source_hash"],
                    "reused_exact_text": review["ad_id"] != ad["id"],
                }
        result.append(ad | {"portrayal_review": attached})
    return result


def validate_portrayal_review(ad: dict, codebook: dict) -> None:
    review = ad.get("portrayal_review", {})
    if review.get("status") not in ("reviewed", "uncertain", "unreviewed", "stale"):
        raise ValueError("Invalid attached portrayal review status")
    if review["status"] in ("reviewed", "uncertain"):
        if review_key(ad) != review_key(review):
            raise ValueError("Portrayal review identity binding changed")
        for description in review["descriptions"]:
            validate_description(description, ad["text"], codebook)
    elif review["descriptions"]:
        raise ValueError("Unreviewed or stale ads cannot contain counted descriptions")


def in_scope(description: dict, party: str, scope: str) -> bool:
    if description["voice"] not in VOICES:
        return False
    person = description["target_kind"] == "person"
    opponent = description["target_role"] == "opponent"
    cross_party = description["target_party"] in PARTIES and description["target_party"] != party
    if scope == "opponents":
        return person and opponent and cross_party
    if scope == "self":
        return person and description["target_role"] == "self_or_supported"
    if scope == "same_party_opponents":
        return person and opponent and description["target_party"] == party
    if scope == "collective_opponents":
        return not person and opponent and cross_party
    raise ValueError(f"Unknown portrayal scope: {scope}")


def metric(ads: list[dict], total: int) -> dict:
    ids = [ad["id"] for ad in ads]
    return {
        "count": len(ids),
        "total": total,
        "share": len(ids) / total if total else None,
        "ad_ids": ids,
    }


def tone_category(descriptions: list[dict]) -> str:
    tones = {description["tone"] for description in descriptions}
    if "positive" in tones and "negative" in tones:
        return "mixed"
    if "negative" in tones:
        return "negative_only"
    if "positive" in tones:
        return "positive_only"
    if tones == {"neutral"}:
        return "neutral_only"
    raise ValueError("No portrayal is not a neutral portrayal")


def scope_summary(messages: list[dict], codebook: dict, scope: str) -> dict:
    result = {}
    for party in PARTIES:
        reviewed = [
            ad
            for ad in messages
            if ad["alignment"] == party
            and ad.get("portrayal_review", {}).get("status") == "reviewed"
        ]
        descriptions = {
            ad["id"]: [
                description
                for description in ad["portrayal_review"]["descriptions"]
                if in_scope(description, party, scope)
            ]
            for ad in reviewed
        }
        eligible = [ad for ad in reviewed if descriptions[ad["id"]]]
        total = len(eligible)
        result[party] = {
            "described": metric(eligible, len(reviewed)),
            "no_description": metric(
                [ad for ad in reviewed if not descriptions[ad["id"]]], len(reviewed)
            ),
            "tones": {
                tone: metric(
                    [ad for ad in eligible if tone_category(descriptions[ad["id"]]) == tone], total
                )
                for tone in TONES
            },
            "inclusive_tones": {
                tone: metric(
                    [
                        ad
                        for ad in eligible
                        if any(d["tone"] == tone for d in descriptions[ad["id"]])
                    ],
                    total,
                )
                for tone in ("negative", "positive")
            },
            "frames": {
                frame: metric(
                    [
                        ad
                        for ad in eligible
                        if any(d["frame"] == frame for d in descriptions[ad["id"]])
                    ],
                    total,
                )
                for frame in codebook["frames"]
            },
        }
    return result


def portrayal_summary(ads: list[dict], codebook: dict) -> dict:
    messages = unique_messages([ad for ad in ads if ad["alignment"] in PARTIES])
    coverage = {}
    for party in PARTIES:
        group = [ad for ad in messages if ad["alignment"] == party]
        coverage[party] = {
            status: metric(
                [
                    ad
                    for ad in group
                    if ad.get("portrayal_review", {}).get("status", "unreviewed") == status
                ],
                len(group),
            )
            for status in ("reviewed", "uncertain", "unreviewed", "stale")
        }
    excluded = {}
    for party in PARTIES:
        counts = Counter(publisher(ad) for ad in ads if ad["alignment"] == party)
        if counts:
            excluded[party] = min(counts, key=lambda name: (-counts[name], name))
    reduced = unique_messages(
        [
            ad
            for ad in ads
            if ad["alignment"] in PARTIES and publisher(ad) != excluded.get(ad["alignment"])
        ]
    )
    evidence = [
        {
            **description,
            "ad_id": ad["id"],
            "party": ad["alignment"],
            "sponsor": ad["sponsor"],
            "source": ad["source"],
            "source_url": ad["source_url"],
            "source_hash": ad["source_hash"],
            "review_source_hash": ad["portrayal_review"]["source_hash"],
            "text_hash": ad["text_hash"],
            "review_status": ad["portrayal_review"]["status"],
        }
        for ad in messages
        if ad.get("portrayal_review", {}).get("status") in ("reviewed", "uncertain")
        for description in ad["portrayal_review"]["descriptions"]
    ]
    return {
        "version": codebook["version"],
        "method": codebook["method"],
        "denominator": "Exact party/messages deduplicated after filters. Tone/frame shares use "
        "reviewed messages with an endorsed, in-scope description. No description is not neutral. "
        "Negative-only / positive-only / mixed / neutral-only are mutually exclusive. "
        "Mixed means positive and negative descriptions in that scope, "
        "possibly of different people. "
        "Inclusive negative and positive overlap through mixed messages; frames also overlap.",
        "coverage": coverage,
        "scopes": {scope: scope_summary(messages, codebook, scope) for scope in SCOPES},
        "sensitivity": {
            "excluded_publishers": excluded,
            "scopes": {
                scope: scope_summary(reduced, codebook, scope) for scope in ("opponents", "self")
            },
        },
        "evidence": evidence,
    }
