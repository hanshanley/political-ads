from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import date, timedelta

from political_ads.schema import digest, message_key

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
                "issues": matches(ad["text"], codebook["issues"]),
                "portrayal_markers": matches(ad["text"], codebook["portrayal_language"]),
                "text_hash": digest(ad["text"]),
                "message_id": message_key(ad["text"]),
            }
        )
    return result


def unique_messages(ads: list[dict]) -> list[dict]:
    unique = {}
    for ad in sorted(ads, key=lambda a: (a["published"], a["id"])):
        unique.setdefault((ad["alignment"], ad["message_id"]), ad)
    return list(unique.values())


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
        tokens = re.findall(r"[a-z]+(?:['’][a-z]+)?", ad["text"].casefold())
        phrases = {
            " ".join(tokens[i : i + n])
            for n in (2, 3)
            for i in range(len(tokens) - n + 1)
            if tokens[i] not in STOP
            and tokens[i + n - 1] not in STOP
            and len(" ".join(tokens[i : i + n])) > 7
        }
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
        day = date.fromisoformat(ad["published"])
        week = (day - timedelta(days=day.weekday())).isoformat()
        if ad["alignment"] in {"D", "R"}:
            weeks[week][ad["alignment"]] += 1
    return [{"week": week, **counts} for week, counts in sorted(weeks.items())]
