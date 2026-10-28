from __future__ import annotations

import math
import re
from datetime import date, timedelta

from textblob.en import sentiment

from political_ads.analysis import lexical_chunks, publisher, unique_messages
from political_ads.registry import candidate_alias
from political_ads.schema import START, digest, observation_date

TOKEN = re.compile(r"[^\W\d_]+(?:[-'][^\W\d_]+)*")
PARTIES = {
    "D": re.compile(r"\b(?:democrats?|democratic\s+party)\b", re.I),
    "R": re.compile(r"\b(?:republicans?|gop)\b", re.I),
}
METHOD = (
    "Exploratory nearby-word analysis, not a sentiment or target-attribution classifier. "
    "TextBlob's bundled English lexicon supplies words with a nonzero adjective polarity; "
    "no polarity score is assigned to an ad. Words are not contextually POS-tagged. "
    "Exact full candidate names and explicit party names identify mention contexts, not "
    "grammatical targets. Mixed-party sentences are excluded. A lexicon word must be "
    "within 12 tokens of a mention in the same sentence and evidence lane, and cannot "
    "be part of the name itself. Quotations, negation, self-description, policy descriptions "
    "and approval lines remain possible; original wording is never repaired. "
    "Each exact party/message counts once per word. Denominators include all messages "
    "with an eligible mention context, including those without a lexicon-word hit. "
    "Rankings require 10 messages in each group and support in 3 messages in one group. "
    "Log2 message-presence odds ratios use a 0.5 correction in each cell; a ratio is not "
    "a significance test. Candidate, source, format and election-phase mixes are not matched."
)


def adjective_vocabulary() -> set[str]:
    return {
        word
        for word, senses in sentiment.items()
        if "JJ" in senses and senses["JJ"][0] != 0 and TOKEN.fullmatch(word)
    }


def mention_contexts(ad: dict, aliases: list[dict], vocabulary: set[str]) -> tuple[set, list]:
    names = []
    for candidate in [*ad.get("candidate_mentions", []), *aliases]:
        party = {"DEM": "D", "REP": "R"}.get(candidate["party"])
        alias = candidate_alias(candidate)
        if party and alias:
            pattern = r"(?<!\w)" + r"\s+".join(map(re.escape, alias.split())) + r"(?!\w)"
            names.append((party, re.compile(pattern, re.I), candidate["candidate_id"]))
    targets, evidence = set(), []
    for lane_start, lane in lexical_chunks(ad):
        for sentence in re.finditer(r"[^.!?]+(?:[.!?]+|$)", lane):
            text = sentence.group()
            offset = lane_start + sentence.start()
            mentions = [
                {"party": party, "start": m.start(), "end": m.end(), "text": m.group()}
                for party, pattern in PARTIES.items()
                for m in pattern.finditer(text)
            ]
            mentions += [
                {
                    "party": party,
                    "start": m.start(),
                    "end": m.end(),
                    "text": m.group(),
                    "candidate_id": identity,
                }
                for party, pattern, identity in names
                for m in pattern.finditer(text)
            ]
            parties = {m["party"] for m in mentions}
            if len(parties) != 1:
                continue
            target = parties.pop()
            targets.add(target)
            tokens = list(TOKEN.finditer(text))
            for index, token in enumerate(tokens):
                if token.group().casefold() not in vocabulary:
                    continue
                if any(m["start"] < token.end() and m["end"] > token.start() for m in mentions):
                    continue
                start = tokens[max(0, index - 12)].start()
                end = tokens[min(len(tokens) - 1, index + 12)].end()
                nearby = [m for m in mentions if m["start"] < end and m["end"] > start]
                if nearby:
                    start = min(start, *(m["start"] for m in nearby))
                    end = max(end, *(m["end"] for m in nearby))
                    evidence.append(
                        {
                            "ad_id": ad["id"],
                            "source_hash": ad["source_hash"],
                            "source_url": ad.get("source_url"),
                            "party": ad["alignment"],
                            "target_party": target,
                            "word": token.group().casefold(),
                            "text": token.group(),
                            "start": offset + token.start(),
                            "end": offset + token.end(),
                            "context": text[start:end],
                            "context_start": offset + start,
                            "context_end": offset + end,
                            "sentence_start": offset,
                            "sentence_end": offset + len(text),
                            "mentions": [
                                m | {"start": offset + m["start"], "end": offset + m["end"]}
                                for m in nearby
                            ],
                            "status": "unreviewed_mention_cooccurrence",
                        }
                    )
    return targets, evidence


def word_comparison(groups: dict, words_by_ad: dict, minimum: int, minimum_total: int) -> dict:
    coverage = {
        name: {"total": len(ads), "ad_ids": [ad["id"] for ad in ads]}
        for name, ads in groups.items()
    }
    words = sorted(
        {word for ads in groups.values() for ad in ads for word in words_by_ad[ad["id"]]}
    )
    rows = []
    first, second = groups
    rankable = all(scope["total"] >= minimum_total for scope in coverage.values())
    for word in words:
        row = {"word": word}
        for name, ads in groups.items():
            ids = [ad["id"] for ad in ads if word in words_by_ad[ad["id"]]]
            row[name] = {
                "count": len(ids),
                "total": len(ads),
                "share": len(ids) / len(ads) if ads else None,
                "ad_ids": ids,
            }
        if max(row[name]["count"] for name in groups) < minimum:
            continue
        odds = {
            name: (row[name]["count"] + 0.5) / (row[name]["total"] - row[name]["count"] + 0.5)
            for name in groups
        }
        row["log2_odds"] = math.log2(odds[first] / odds[second]) if rankable else None
        rows.append(row)
    return {
        "coverage": coverage,
        "rankable": rankable,
        "words": sorted(rows, key=lambda row: (-(row["log2_odds"] or 0), row["word"])),
        "positive_direction": first,
    }


def descriptive_language(dataset: dict, aliases: list[dict] | None = None) -> dict:
    vocabulary = adjective_vocabulary()
    ads = [ad for ad in unique_messages(dataset["ads"]) if ad["alignment"] in PARTIES]
    contexts, evidence = {}, []
    for ad in ads:
        contexts[ad["id"]], hits = mention_contexts(ad, aliases or [], vocabulary)
        evidence.extend(hits)
    words_by_target = {target: {ad["id"]: set() for ad in ads} for target in PARTIES}
    for hit in evidence:
        words_by_target[hit["target_party"]][hit["ad_id"]].add(hit["word"])
    targets = {
        target: word_comparison(
            {
                party: [
                    ad for ad in ads if ad["alignment"] == party and target in contexts[ad["id"]]
                ]
                for party in PARTIES
            },
            words_by_target[target],
            minimum=3,
            minimum_total=10,
        )
        for target in PARTIES
    }
    end = date.fromisoformat(dataset["until"])
    recent_start = end - timedelta(days=89)
    previous_start = recent_start - timedelta(days=90)
    bounds = {
        "recent": (recent_start.isoformat(), end.isoformat()),
        "previous": (previous_start.isoformat(), (recent_start - timedelta(days=1)).isoformat()),
    }
    changes = {}
    for party, target in (("D", "R"), ("R", "D")):
        periods = {
            name: [
                ad
                for ad in ads
                if ad["alignment"] == party
                and target in contexts[ad["id"]]
                and start <= observation_date(ad) <= stop
            ]
            for name, (start, stop) in bounds.items()
        }
        common = set.intersection(*({publisher(ad) for ad in group} for group in periods.values()))
        changes[party] = {
            "target_party": target,
            "all_publishers": word_comparison(periods, words_by_target[target], 3, 10),
            "common_publishers": word_comparison(
                {
                    name: [ad for ad in group if publisher(ad) in common]
                    for name, group in periods.items()
                },
                words_by_target[target],
                3,
                10,
            ),
            "common_publisher_names": sorted(common),
        }
    return {
        "version": "mention-lexicon-1",
        "snapshot_id": dataset["snapshot_id"],
        "method": METHOD,
        "lexicon": {
            "name": "TextBlob 0.19 bundled English adjective-polarity vocabulary",
            "word_count": len(vocabulary),
            "sha256": digest("\n".join(sorted(vocabulary))),
        },
        "minimum_support": 3,
        "minimum_group_total": 10,
        "scope_start": START,
        "reviewed_aliases": aliases or [],
        "targets": targets,
        "periods": {name: {"start": start, "end": stop} for name, (start, stop) in bounds.items()},
        "changes": changes,
        "evidence": evidence,
    }
