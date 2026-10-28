from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import date, timedelta

from political_ads.schema import digest, message_key, observation_date

STOP = set(
    "a an and are as at be been but by for from had has have he her him his i if in is it "
    "its me my not of on or our out s she so t than that the their them then there they this "
    "to too us was we were what when who will with you your i'm approve message voice over "
    "narrator".split()
)


def matches(text: str, families: dict[str, list[str]]) -> list[dict]:
    found = []
    for label, phrases in families.items():
        seen = set()
        for phrase in phrases:
            pattern = r"\s+".join(re.escape(word) for word in phrase.split())
            for match in re.finditer(r"(?<!\w)" + pattern + r"(?!\w)", text, re.I):
                key = (match.start(), match.end())
                if key not in seen:
                    found.append(
                        {
                            "label": label,
                            "text": match.group(),
                            "start": match.start(),
                            "end": match.end(),
                        }
                    )
                    seen.add(key)
    return sorted(found, key=lambda match: (match["start"], match["end"], match["label"]))


def lexical_chunks(ad: dict) -> list[tuple[int, str]]:
    segments = ad.get("segments", [])
    if not any(s.get("kind") in {"local_asr", "video_ocr"} for s in segments):
        return [(0, ad["text"])]
    chunks = []
    offset = 0
    previous = None
    for segment in segments:
        if previous == "local_asr" and segment["kind"] == previous:
            start, text = chunks[-1]
            chunks[-1] = (start, text + "\n" + segment["text"])
        else:
            chunks.append((offset, segment["text"]))
        offset += len(segment["text"]) + 1
        previous = segment["kind"]
    return chunks


def ad_matches(ad: dict, families: dict[str, list[str]]) -> list[dict]:
    return [
        match | {"start": match["start"] + offset, "end": match["end"] + offset}
        for offset, text in lexical_chunks(ad)
        for match in matches(text, families)
    ]


def apply_reviews(ads: list[dict], ledger: dict) -> list[dict]:
    by_id = {ad["id"]: ad for ad in ads}
    examples = []
    for record in ledger["examples"]:
        ad = by_id.get(record["ad_id"])
        # A filtered snapshot can legitimately omit a reviewed ad.
        if ad is None:
            continue
        if ad["source_hash"] != record["source_hash"] or record["quote"] not in ad["text"]:
            raise ValueError(f"Review evidence changed for {ad['id']}; re-review before publishing")
        if ad["alignment"] == record["target_party"]:
            raise ValueError("An opponent example cannot target its advertiser's own party")
        start = ad["text"].index(record["quote"])
        examples.append(
            record
            | {
                "start": start,
                "end": start + len(record["quote"]),
                "party": ad["alignment"],
                "race": ad["race"],
                "source_url": ad["source_url"],
                "published": ad["published"],
            }
        )
    return examples


def annotate(ads: list[dict], codebook: dict) -> list[dict]:
    result = []
    for ad in ads:
        result.append(
            ad
            | {
                "issues": ad_matches(ad, codebook["issues"]),
                "portrayal_markers": ad_matches(ad, codebook["portrayal_language"]),
                "text_hash": digest(ad["text"]),
                "message_id": message_key(ad["text"]),
            }
        )
    return result


def unique_messages(ads: list[dict]) -> list[dict]:
    unique = {}
    for ad in sorted(ads, key=lambda a: (observation_date(a), a["id"])):
        unique.setdefault((ad["alignment"], ad["message_id"]), ad)
    return list(unique.values())


def publisher(ad: dict) -> str:
    return ad.get("sponsor") or (
        ad["source"]
        .removesuffix("-media")
        .removesuffix("-images")
        .removesuffix("-google")
        .removesuffix("-snap")
    )


def comparison(ads: list[dict], labels: list[str], field: str = "issues") -> list[dict]:
    unique = unique_messages(ads)
    result = []
    for label in sorted(labels):
        row = {"label": label}
        for party in ("D", "R"):
            scope = [a for a in unique if a["alignment"] == party]
            included = [a["id"] for a in scope if any(m["label"] == label for m in a[field])]
            row[party] = {
                "count": len(included),
                "total": len(scope),
                "share": len(included) / len(scope) if scope else None,
                "ad_ids": included,
            }
        result.append(row)
    return result


def distinctive_phrases(ads: list[dict], minimum: int = 3) -> dict:
    counts = {"D": Counter(), "R": Counter()}
    for ad in unique_messages(ads):
        if ad["alignment"] not in counts:
            continue
        phrases = set()
        for _, text in lexical_chunks(ad):
            tokens = re.findall(r"[a-z]+(?:['’][a-z]+)?", text.casefold())
            phrases.update(
                " ".join(tokens[i : i + n])
                for n in (2, 3)
                for i in range(len(tokens) - n + 1)
                if tokens[i] not in STOP
                and tokens[i + n - 1] not in STOP
                and len(" ".join(tokens[i : i + n])) > 7
            )
        counts[ad["alignment"]].update(phrases)
    totals = {party: sum(counter.values()) for party, counter in counts.items()}
    result = {}
    vocabulary = set(counts["D"]) | set(counts["R"])
    for party, other in (("D", "R"), ("R", "D")):
        scores = []
        for phrase in vocabulary:
            own, theirs = counts[party][phrase], counts[other][phrase]
            if own < minimum:
                continue
            odds = math.log((own + 0.5) / (totals[party] - own + 0.5))
            odds -= math.log((theirs + 0.5) / (totals[other] - theirs + 0.5))
            scores.append(
                {
                    "phrase": phrase,
                    "messages": own,
                    "other_messages": theirs,
                    "log_odds": round(odds, 4),
                }
            )
        result[party] = sorted(scores, key=lambda row: (-row["log_odds"], row["phrase"]))[:15]
    return result


def timeline(ads: list[dict]) -> list[dict]:
    weeks = defaultdict(lambda: {"D": 0, "R": 0})
    for ad in unique_messages(ads):
        day = date.fromisoformat(observation_date(ad))
        week = (day - timedelta(days=day.weekday())).isoformat()
        if ad["alignment"] in {"D", "R"}:
            weeks[week][ad["alignment"]] += 1
    return [{"week": week, **counts} for week, counts in sorted(weeks.items())]


def stratified_comparisons(ads: list[dict], codebook: dict) -> dict:
    def category(ad, field):
        if field == "placement":
            return ad.get("placement", "campaign_release")
        if field == "record_format":
            segment = (ad.get("segments") or [{}])[0]
            return (
                segment.get("reported_platform", "google")
                + "_"
                + segment["reported_ad_type"].lower()
                if segment.get("reported_ad_type")
                else segment.get("kind", "unknown")
            )
        return publisher(ad) if field == "source" else ad[field]

    def summarize(records, messages=None):
        messages = unique_messages(records) if messages is None else messages
        coverage = {}
        for party in ("D", "R"):
            party_records = [ad for ad in records if ad["alignment"] == party]
            party_messages = [ad for ad in messages if ad["alignment"] == party]
            coverage[party] = {
                "records": len(party_records),
                "messages": len(party_messages),
                "publishers": sorted({publisher(ad) for ad in party_records}),
                "record_ad_ids": [ad["id"] for ad in party_records],
                "message_ad_ids": [ad["id"] for ad in party_messages],
            }
        return {
            "coverage": coverage,
            "issues": comparison(messages, list(codebook["issues"])),
            "portrayals": comparison(
                messages, list(codebook["portrayal_language"]), "portrayal_markers"
            ),
        }

    first_messages = unique_messages(ads)
    result = {"overall": summarize(ads)}
    result["month"] = {
        month: summarize(
            [ad for ad in ads if observation_date(ad)[:7] == month],
            [ad for ad in first_messages if observation_date(ad)[:7] == month],
        )
        for month in sorted({observation_date(ad)[:7] for ad in ads})
    }
    for field in (
        "chamber",
        "sponsor_type",
        "source",
        "race",
        "phase",
        "placement",
        "record_format",
    ):
        result[field] = {
            value: summarize([ad for ad in ads if category(ad, field) == value])
            for value in sorted({category(ad, field) for ad in ads})
        }
    excluded = {}
    for party in ("D", "R"):
        publishers = Counter(publisher(ad) for ad in ads if ad["alignment"] == party)
        if publishers:
            excluded[party] = min(publishers, key=lambda source: (-publishers[source], source))
    result["sensitivity"] = {
        "excluded_publishers": excluded,
        "without_largest_publisher_per_party": summarize(
            [ad for ad in ads if publisher(ad) != excluded.get(ad["alignment"])]
        ),
    }
    return result
