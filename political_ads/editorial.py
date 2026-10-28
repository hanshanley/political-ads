from __future__ import annotations

import re
from collections import Counter
from html import escape

from political_ads.analysis import unique_messages
from political_ads.figures import NAMES
from political_ads.portrayals import in_scope
from political_ads.schema import END


def context_illustrations(dataset: dict, ledger: dict) -> list[dict]:
    by_id = {ad["id"]: ad for ad in dataset["ads"]}
    results = []
    for review in ledger.get("reviews", []):
        ad = by_id.get(review["ad_id"])
        if ad is None:
            continue
        if (
            ad["source_hash"] != review["source_hash"]
            or ad["alignment"] != review["alignment"]
            or review["quote"] not in ad["text"]
            or not re.search(r"\b" + re.escape(review["word"]) + r"\b", review["quote"], re.I)
        ):
            raise ValueError(f"Descriptor editorial evidence changed: {ad['id']}; re-review")
        start = ad["text"].index(review["quote"])
        results.append(
            review
            | {"start": start, "end": start + len(review["quote"]), "source_url": ad["source_url"]}
        )
    return results


def representative_portrayals(
    portrayals: dict, party: str, scope: str, limit: int = 3
) -> list[dict]:
    eligible = [
        hit
        for hit in portrayals["evidence"]
        if hit["party"] == party
        and hit["review_status"] == "reviewed"
        and in_scope(hit, party, scope)
    ]
    frames = portrayals["scopes"][scope][party]["frames"]
    selected = []
    used = set()
    for frame in sorted(frames, key=lambda key: (-frames[key]["count"], key)):
        candidates = [hit for hit in eligible if hit["frame"] == frame and hit["ad_id"] not in used]
        if not candidates:
            continue
        counts = Counter()
        for phrase in {hit["phrase"].strip().casefold() for hit in candidates}:
            counts[phrase] = len(
                {hit["ad_id"] for hit in candidates if hit["phrase"].strip().casefold() == phrase}
            )
        hit = min(
            candidates,
            key=lambda item: (
                -counts[item["phrase"].strip().casefold()],
                len(item["quote"]),
                item["ad_id"],
                item["target"],
                item["phrase"],
            ),
        )
        selected.append(hit)
        used.add(hit["ad_id"])
        if len(selected) == limit:
            break
    return selected


def portrayal_excerpt(hit: dict, limit: int = 22) -> str:
    quote = hit["quote"]
    tokens = list(re.finditer(r"\S+", quote))
    phrase_start = quote.index(hit["phrase"])
    phrase_token = sum(token.end() <= phrase_start for token in tokens)
    phrase_end = sum(token.start() < phrase_start + len(hit["phrase"]) for token in tokens)
    preceding = max(0, (limit - len(hit["phrase"].split())) // 2)
    start = max(0, phrase_token - preceding)
    end = min(max(start + limit, phrase_end), len(tokens))
    return (
        ("... " if start else "")
        + quote[tokens[start].start() : tokens[end - 1].end()]
        + (" ..." if end < len(tokens) else "")
    )


def article_data(dataset: dict, strata: dict, portrayals: dict, figures: dict) -> dict:
    blocks = []
    charts = {chart["id"]: chart for chart in figures["charts"]}
    frames = dataset["portrayal_codebook"]["frames"]
    counts = Counter(ad["alignment"] for ad in dataset["ads"])
    coverage = strata["overall"]["coverage"]
    examples = []

    def paragraph(text):
        blocks.append({"kind": "paragraph", "text": text})

    def heading(text):
        blocks.append({"kind": "heading", "text": text})

    def figure(identity):
        if identity in charts:
            blocks.append({"kind": "figure", **charts[identity]})

    def ratio(value):
        return (
            f"{value['count']:,}/{value['total']:,} ({value['share']:.1%})"
            if value["total"]
            else "no eligible messages"
        )

    opponents = portrayals["scopes"]["opponents"]
    contrasts = []
    if all(opponents[party]["described"]["count"] for party in ("D", "R")):
        for party, other in (("D", "R"), ("R", "D")):
            frame = max(
                frames,
                key=lambda key: (
                    opponents[party]["frames"][key]["share"]
                    - opponents[other]["frames"][key]["share"],
                    key,
                ),
                default=None,
            )
            if frame and (
                opponents[party]["frames"][frame]["share"]
                > opponents[other]["frames"][frame]["share"]
            ):
                contrasts.append(
                    f"{NAMES[party]} ads put more emphasis on "
                    f"{frames[frame].lower()} "
                    f"({ratio(opponents[party]['frames'][frame])}, compared with "
                    f"{ratio(opponents[other]['frames'][frame])} on the other side)"
                )
    if contrasts:
        paragraph(
            "The recovered ads differ in the reputations they build and attack. Among "
            "reviewed messages describing opposing-party people, "
            + "; ".join(contrasts)
            + ". These are the largest observed frame gaps in each direction, not "
            "national estimates or evidence of a pure party effect."
        )
    paragraph(
        "This comparison asks who an ad describes, what it says about that person, and "
        "whether it attacks an opponent or praises its own candidate. It reads descriptions "
        "in context, rather than treating an angry word or a word near a name as a portrayal."
    )
    paragraph(
        f"The saved collection through {dataset['until']} contains "
        f"{len(dataset['ads']):,} English ad-text records: {counts['D']:,} Democratic-aligned, "
        f"{counts['R']:,} Republican-aligned, {counts['other']:,} other and "
        f"{counts['unknown']:,} unresolved. After exact-message deduplication, the D/R "
        f"comparison contains {coverage['D']['messages']:,} and "
        f"{coverage['R']['messages']:,} messages. These are recovered ad releases, "
        "previews and creatives, not all ads aired, and there is no exposure or spending weight."
    )
    heading("First, what has been reviewed?")
    for party in ("D", "R"):
        reviewed = portrayals["coverage"][party]
        paragraph(
            f"{NAMES[party]}-aligned messages: {ratio(reviewed['reviewed'])} reviewed; "
            f"{reviewed['uncertain']['count']:,} uncertain, "
            f"{reviewed['unreviewed']['count']:,} unreviewed and "
            f"{reviewed['stale']['count']:,} stale. Only reviewed messages enter the "
            "description rates below. Missing evidence is not neutral language."
        )
    paragraph(
        "These are AI-assisted full-text contextual labels, not independently validated "
        "human judgments. Exact passages, target anchors and input hashes are retained. "
        "A reported allegation is a portrayal, not this project's finding that it is true."
    )
    figure("portrayal-coverage")
    for scope, prefix, title in (
        ("opponents", "opponent", "How they describe the other side"),
        ("self", "self", "How they describe their own candidates"),
    ):
        heading(title)
        paragraph(
            "This comparison counts endorsed descriptions of named people. Opposing-party "
            "collectives and same-party primary rivals are reported separately in the "
            "technical report. Quoted opponents and allegations being rebutted do not "
            "become the advertiser's own views."
            if scope == "opponents"
            else "The same definitions apply to the advertiser's own or supported candidates. "
            "Supporting a candidate is not itself a positive personality description: "
            "the ad must actually attribute a quality, background, conduct or record. "
            "Policy pledges count as attributed commitments, not accomplished results."
        )
        for party in ("D", "R"):
            group = portrayals["scopes"][scope][party]
            tone = group["tones"]
            paragraph(
                f"{NAMES[party]} ads have an eligible description in "
                f"{ratio(group['described'])} reviewed messages; "
                f"{group['no_description']['count']:,} have no description in this scope. "
                "Among messages with a description, "
                + "; ".join(
                    f"{label}: {ratio(tone[key])}"
                    for key, label in (
                        ("negative_only", "negative only"),
                        ("positive_only", "positive only"),
                        ("mixed", "both positive and negative"),
                        ("neutral_only", "neutral only"),
                    )
                )
                + "."
            )
            paragraph(
                "Including mixed messages, the share with any negative portrayal is "
                f"{ratio(group['inclusive_tones']['negative'])}; the share with any "
                f"positive portrayal is {ratio(group['inclusive_tones']['positive'])}. "
                "Those two percentages overlap; they are not competing pieces of one total."
            )
        figure(f"{prefix}-tone")
        for party in ("D", "R"):
            group = portrayals["scopes"][scope][party]
            ranked = sorted(group["frames"], key=lambda key: (-group["frames"][key]["count"], key))
            top = [key for key in ranked if group["frames"][key]["count"]][:3]
            if top:
                paragraph(
                    f"The most common {NAMES[party]} description frames in this scope are "
                    + "; ".join(
                        f"{frames[key].lower()} ({ratio(group['frames'][key])})" for key in top
                    )
                    + ". A message can use several frames, so these percentages overlap."
                )
            for hit in representative_portrayals(portrayals, party, scope):
                examples.append(hit | {"scope": scope})
                blocks.append(
                    {
                        "kind": "quote",
                        "text": portrayal_excerpt(hit),
                        "source_url": hit["source_url"],
                        "caption": f"{NAMES[party]}-aligned {hit['sponsor']} on {hit['target']}: "
                        f"{hit['tone']}; {frames[hit['frame']].lower()}. "
                        f"Voice: {hit['voice'].replace('_', ' ')}. Ad {hit['ad_id']}.",
                    }
                )
        figure(f"{prefix}-frames")
    heading("Are these party differences or differences in the sources?")
    exclusions = portrayals["sensitivity"]["excluded_publishers"]
    paragraph(
        "A source-mix check removes each party's largest publisher by record count "
        "and deduplicates again: "
        + "; ".join(f"{NAMES[p]}: {name}" for p, name in exclusions.items())
        + ". This cannot turn an opportunistic collection into a representative sample."
    )
    for party in ("D", "R"):
        full = portrayals["scopes"]["opponents"][party]["inclusive_tones"]["negative"]
        reduced = portrayals["sensitivity"]["scopes"]["opponents"][party]["inclusive_tones"][
            "negative"
        ]
        paragraph(
            f"For {NAMES[party]} ads describing opposing-party people, any-negative "
            f"portrayals change from {ratio(full)} to {ratio(reduced)} after that exclusion. "
            "Differences can still reflect races, phases, extraction formats and repeated "
            "changed-target templates, not a pure party effect."
        )
    figure("publisher-composition")
    heading("The issues and collection history are supporting context")
    paragraph(
        "The following charts remain lexical and descriptive of collection coverage. "
        "An issue phrase in a quotation is still a match; these are not person-tone "
        "labels or measures of how much either party advertised."
    )
    figure("issue-language")
    figure("source-sensitivity")
    figure("monthly-coverage")
    figure("monthly-issues")
    heading("What the evidence can establish")
    paragraph(
        "This identifies attributed descriptions in the recovered text. It cannot "
        "establish national prevalence, factual truth, persuasion or voter exposure. "
        "ASR/OCR can misrecognize names and negation. Sparse Republican House and "
        "early-cycle coverage remain limitations; missing ads are not evidence of silence."
    )
    paragraph(
        "Illustrations are selected from the three most frequent frames per party/scope, "
        "using the most repeated exact descriptor phrase and then the shortest supporting "
        "passage, with ad ID as a tie-breaker and no repeated message within a scope. "
        "They illustrate the coded frames, not a representative sample or an intensity ranking."
    )
    paragraph(
        f"The final eligibility cutoff remains {END}, inclusive. This snapshot stops "
        f"at {dataset['until']}. Automatic research refresh can add unreviewed evidence "
        "but does not silently classify it. Both editions remain unpublished; website "
        "and Substack publication and host integration remain on hold."
    )
    return {
        "version": "article-2",
        "snapshot_id": dataset["snapshot_id"],
        "publication_status": "draft_not_published",
        "until": dataset["until"],
        "title": "How Democrats and Republicans describe each other",
        "subtitle": "Opponents, their own candidates, and the balance of "
        "negative and positive portrayals.",
        "blocks": blocks,
        "portrayal_examples": examples,
        "record_counts": dict(counts),
        "message_ad_ids": {p: coverage[p]["message_ad_ids"] for p in ("D", "R")},
        "total_unique_messages": len(unique_messages(dataset["ads"])),
    }


def substack_markdown(article: dict) -> str:
    lines = [
        f"# {article['title']}",
        article["subtitle"],
        "**DRAFT - NOT PUBLISHED.** Prepared for Substack; images are local PNG files. "
        "No upload, scheduling or publication has occurred.",
        f"Data through {article['until']}. Snapshot `{article['snapshot_id']}`.",
    ]
    for block in article["blocks"]:
        if block["kind"] == "heading":
            lines.append("## " + block["text"])
        elif block["kind"] == "paragraph":
            lines.append(block["text"])
        elif block["kind"] == "quote":
            lines.append("> " + block["text"].replace("\n", "\n> "))
            lines.append(block["caption"] + f" [Original source]({block['source_url']}).")
        elif block["kind"] == "figure":
            lines.append(f"![{block['description']}](figures/{block['png']})")
            lines.append(f"*{block['description']}* [Exact data](figures/{block['csv']}).")
    lines.extend(
        [
            "## Evidence and methods",
            "[Complete text and evidence (CSV)](analysis-ads.csv) | "
            "[Complete local analysis (JSON)](analysis.json) | [Technical report](analysis.html) | "
            "[All chart data](figures/chart-data.json) | "
            "[Context-coded portrayals](figures/portrayal-evidence.json)",
            "For a future Substack edition, upload the PNGs and replace the local evidence "
            "links only after an authorized destination exists. These draft links do not "
            "claim that any public page or download is live.",
        ]
    )
    return "\n\n".join(lines) + "\n"


def margin_html(article: dict, *, web: bool = False) -> str:
    blocks = []
    for block in article["blocks"]:
        if block["kind"] == "heading":
            blocks.append(f"<h2>{escape(block['text'])}</h2>")
        elif block["kind"] == "paragraph":
            blocks.append(f"<p>{escape(block['text'])}</p>")
        elif block["kind"] == "quote":
            blocks.append(
                f"<blockquote>{escape(block['text'])}</blockquote>"
                f"<p class='caption'>{escape(block['caption'])} "
                f"<a href='{escape(block['source_url'], quote=True)}'>Original source</a>.</p>"
            )
        elif block["kind"] == "figure":
            blocks.append(
                f"<figure><a href='figures/{escape(block['png'])}'>"
                f"<img loading='lazy' src='figures/{escape(block['png'])}' "
                f"alt='{escape(block['description'], quote=True)}'></a>"
                f"<figcaption>{escape(block['description'])} "
                f"<a href='figures/{escape(block['csv'])}'>Exact data</a>.</figcaption></figure>"
            )
    csv = "data/ads.csv" if web else "analysis-ads.csv"
    evidence = "data/dataset.json.gz" if web else "analysis.json"
    report = "report.html" if web else "analysis.html"
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='robots' content='noindex,nofollow'>"
        f"<title>{escape(article['title'])} - The Margin of Error draft</title>"
        "<style>body{background:#f7f5f0;color:#242424;font:18px/1.7 Georgia,serif;"
        "max-width:820px;margin:0 auto;padding:32px 22px}header,.caption,figcaption,footer"
        "{font-size:14px;color:#666}h1{font-size:clamp(2rem,6vw,3.3rem);line-height:1.13}"
        "h2{font-size:1.65rem;line-height:1.25;margin-top:3rem}a{color:#3d6f8c}"
        ".draft{border-top:1px solid #d6d3cc;border-bottom:1px solid #d6d3cc;padding:12px 0}"
        ".subtitle{font-size:1.25rem;color:#666}figure{margin:2rem 0}img{width:100%;height:auto}"
        "blockquote{border-left:3px solid #d6d3cc;padding-left:22px;margin:2rem 0 1rem}"
        "code{font-size:12px;overflow-wrap:anywhere}footer{margin-top:3rem}</style></head>"
        "<body><header>The Margin of Error / Political advertising</header><main>"
        f"<h1>{escape(article['title'])}</h1><p class='subtitle'>{escape(article['subtitle'])}</p>"
        "<p class='draft'><strong>DRAFT - NOT PUBLISHED.</strong> Prepared for "
        "The Margin of Error; website publication and host integration remain on hold.</p>"
        f"<p class='caption'>Data through {article['until']}. "
        f"Snapshot <code>{article['snapshot_id']}</code>.</p>"
        + "".join(blocks)
        + f"<h2>Read the evidence</h2><p><a href='{csv}'>Complete text and evidence (CSV)</a> | "
        f"<a href='{evidence}'>Complete evidence (JSON)</a> | "
        f"<a href='{report}'>Technical report</a> | "
        "<a href='figures/chart-data.json'>All chart data</a> | "
        "<a href='figures/portrayal-evidence.json'>Context-coded portrayals</a></p>"
        "</main><footer>Research draft. No website or Substack publication has occurred."
        "</footer></body></html>"
    )
