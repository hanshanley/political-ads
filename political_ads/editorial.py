from __future__ import annotations

import re
from collections import Counter
from html import escape

from political_ads.analysis import unique_messages
from political_ads.figures import NAMES
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
            | {
                "start": start,
                "end": start + len(review["quote"]),
                "source_url": ad["source_url"],
            }
        )
    return results


def article_data(
    dataset: dict, strata: dict, descriptors: dict, figures: dict, ledger: dict
) -> dict:
    blocks = []
    charts = {chart["id"]: chart for chart in figures["charts"]}

    def paragraph(text):
        blocks.append({"kind": "paragraph", "text": text})

    def heading(text):
        blocks.append({"kind": "heading", "text": text})

    def figure(identity):
        if identity in charts:
            blocks.append({"kind": "figure", **charts[identity]})

    counts = Counter(ad["alignment"] for ad in dataset["ads"])
    coverage = strata["overall"]["coverage"]
    paragraph(
        "Political ads tell voters what a campaign wants them to notice: a price, a policy, "
        "an achievement, or something allegedly wrong with the other candidate. Comparing "
        "the words can reveal recurring themes. It is harder to distinguish a real party "
        "difference from the particular publishers, races and ad formats we happened to recover."
    )
    paragraph(
        f"This snapshot contains {len(dataset['ads']):,} English-language ad-text records "
        f"through {dataset['until']}: {counts['D']:,} Democratic-aligned, "
        f"{counts['R']:,} Republican-aligned, {counts['other']:,} other and "
        f"{counts['unknown']:,} unresolved. After exact-text deduplication within each party, "
        f"the D/R comparisons use {coverage['D']['messages']:,} and "
        f"{coverage['R']['messages']:,} messages. These are recovered releases, previews and "
        "original creatives, not a census of advertisements aired or a measure of exposure."
    )
    r_house = sum(ad["alignment"] == "R" and ad["chamber"] == "House" for ad in dataset["ads"])
    paragraph(
        f"Republican House coverage includes {r_house:,} English text records. It remains "
        "uneven: more records from a few campaigns do not establish coverage of every "
        "Republican House candidate. Missing ads are unknown, not evidence of silence."
    )
    heading("The issue-language differences in this collection")
    for party in ("D", "R"):
        available = [row for row in strata["overall"]["issues"] if row[party]["total"]]
        if available:
            row = min(available, key=lambda row: (-row[party]["share"], row["label"]))
            value = row[party]
            paragraph(
                f"The most frequent published issue family on the {NAMES[party]} side is "
                f"{row['label']}: {value['count']:,}/{value['total']:,} exact messages "
                f"({value['share']:.1%}). A match means one of the codebook's phrases appears "
                "in the available text. It is not an independent judgment of the ad's "
                "main topic, accuracy or effectiveness."
            )
    paragraph(
        "Each message contributes at most once to each family. Categories overlap. "
        "There is no spending, impression or airing weight, and an OCR preview is not "
        "equivalent to a complete broadcast transcript."
    )
    figure("issue-language")
    heading("What the ads actually say about opponents")
    paragraph(
        "A small set of source-checked passages makes the difference between wording and "
        "portrayal concrete. The examples below are illustrations, not representative "
        "estimates of how often either party attacks. The report retains the complete "
        "ad text and the review's speaker and target notes."
    )
    examples = []
    for party in ("D", "R"):
        example = next((e for e in dataset["examples"] if e["party"] == party), None)
        if example:
            examples.append(example)
            tokens = list(re.finditer(r"\S+", example["quote"]))
            end = tokens[min(21, len(tokens) - 1)].end()
            blocks.append(
                {
                    "kind": "quote",
                    "text": example["quote"][:end]
                    + (" ..." if end < len(example["quote"]) else ""),
                    "source_url": example["source_url"],
                    "caption": f"{NAMES[party]}-aligned advertiser on {example['target']}. "
                    + example["context"],
                }
            )
    paragraph(
        "The broader phrase-family chart counts vocabulary such as extreme/radical, "
        "trust/integrity and special interests. It includes quoted and denied language "
        "and positive descriptions. Calling it an attack-rate chart would go beyond "
        "what has been measured."
    )
    figure("portrayal-language")
    heading("A closer look at descriptive words")
    paragraph(
        "The next comparison follows the question in the Harris/Trump media-coverage "
        "analysis, but not its assumptions about a different corpus. Here we compare "
        "D- and R-aligned messages in contexts mentioning Democratic candidates or the "
        "party, then do the same for Republican mentions. Full candidate names and "
        "explicit party names are required. Surname-only references, some nicknames and "
        "misrecognized names can be missed."
    )
    paragraph(
        "A bundled general-English lexicon supplies words with adjective-polarity entries. "
        "We do not give advertisements sentiment scores or claim that each occurrence "
        "is grammatically an adjective. Words must be within 12 tokens of an explicit "
        "mention in the same sentence and evidence lane; mixed-party sentences are excluded. "
        "Each exact message counts once per word. The denominator includes eligible "
        "mention-context messages with no lexicon-word hit."
    )
    for target in ("D", "R"):
        group = descriptors["targets"][target]
        paragraph(
            f"For {NAMES[target]} mentions, the eligible denominators are "
            f"{group['coverage']['D']['total']:,} D-aligned and "
            f"{group['coverage']['R']['total']:,} R-aligned messages. These are smaller "
            "and more selective than the issue-chart denominators."
        )
        figure(f"descriptors-{target}")
    paragraph(
        "The horizontal scale is a smoothed log2 message-presence odds ratio, not a "
        "sentiment score or a significance test. Only comparisons with at least ten "
        "messages per group and a word in at least three messages on one side are ranked. "
        "The charts show at most five supported contrasts in either direction; all "
        "supported words and their exact counts remain in the downloads."
    )
    illustrations = context_illustrations(dataset, ledger)
    if illustrations:
        paragraph(
            "Reading the original contexts changes what a tempting headline would imply. "
            "These additional source-bound examples were checked specifically to "
            "illustrate the limitations of proximity, not to validate all extracted contexts."
        )
        for illustration in illustrations:
            blocks.append(
                {
                    "kind": "quote",
                    "text": illustration["quote"],
                    "source_url": illustration["source_url"],
                    "caption": illustration["interpretation"],
                }
            )
    paragraph(
        "A word near a Republican name is not necessarily a word describing that person. "
        "It can describe crime, prices, an opponent's quotation or the advertiser's own "
        "candidate. Negation is retained rather than flipped into a new sentiment label. "
        "Ideological wording missing from the general-English lexicon is addressed "
        "separately by the published phrase families."
    )
    heading("What changes in the last ninety days?")
    periods = descriptors["periods"]
    paragraph(
        f"The recent window is {periods['recent']['start']} to {periods['recent']['end']}; "
        f"the preceding window is {periods['previous']['start']} to "
        f"{periods['previous']['end']}. We compare first-observed exact messages in "
        "contexts mentioning the opposing party, not how long a creative kept airing. "
        "For early-cycle snapshots, windows are limited by the collection's January 1 start."
    )
    for party in ("D", "R"):
        change = descriptors["changes"][party]
        scope, common = change["all_publishers"], change["common_publishers"]
        paragraph(
            f"For {NAMES[party]}-aligned ads, the recent and preceding windows contain "
            f"{scope['coverage']['recent']['total']:,} and "
            f"{scope['coverage']['previous']['total']:,} eligible messages. Keeping only "
            "publishers present in both windows leaves "
            f"{common['coverage']['recent']['total']:,} and "
            f"{common['coverage']['previous']['total']:,}. "
            + (
                "That subset meets the group-size threshold, but it does not hold race, "
                "format, candidate or election phase constant."
                if common["rankable"]
                else "That subset does not meet the group-size threshold, so its word "
                "contrasts are not ranked."
            )
        )
        figure(f"descriptor-change-{party}")
    paragraph(
        "These plots are exploratory changes in the saved collection. A rise can reflect "
        "newly recovered sources or changed-target templates, not a nationwide change "
        "in party strategy. The monthly figures make the uneven historical coverage visible."
    )
    figure("monthly-coverage")
    figure("monthly-issues")
    heading("How much of the difference is the source mix?")
    exclusions = strata["sensitivity"]["excluded_publishers"]
    paragraph(
        "We remove each party's largest publisher by source-record count and recalculate "
        "the exact-message shares. In this snapshot the exclusions are "
        + "; ".join(f"{NAMES[party]}: {name}" for party, name in exclusions.items())
        + ". This is a stress test, not a balanced sample or an estimate corrected "
        "for all missing advertising."
    )
    reduced = {
        row["label"]: row
        for row in strata["sensitivity"]["without_largest_publisher_per_party"]["issues"]
    }
    comparable = [
        row
        for row in strata["overall"]["issues"]
        if all(
            row[p]["share"] is not None and reduced[row["label"]][p]["share"] is not None
            for p in ("D", "R")
        )
    ]
    if comparable:
        row = min(
            comparable,
            key=lambda row: (
                -abs(row["D"]["share"] - row["R"]["share"]),
                row["label"],
            ),
        )
        less = reduced[row["label"]]
        paragraph(
            f"The largest absolute full-sample issue gap is {row['label']}. "
            f"D-aligned messages match it in {row['D']['count']:,}/{row['D']['total']:,} "
            f"({row['D']['share']:.1%}); R-aligned messages in "
            f"{row['R']['count']:,}/{row['R']['total']:,} ({row['R']['share']:.1%}). "
            f"After the exclusions those values are {less['D']['count']:,}/"
            f"{less['D']['total']:,} ({less['D']['share']:.1%}) and "
            f"{less['R']['count']:,}/{less['R']['total']:,} ({less['R']['share']:.1%}). "
            "The changed comparison shows why the original gap should not be read "
            "as a source-independent party effect."
        )
    figure("publisher-composition")
    figure("source-sensitivity")
    heading("What this does - and does not - establish")
    paragraph(
        "This collection supports a checkable description of the words recovered from "
        "these ads, along with a small number of context-reviewed opponent portrayals. "
        "It does not establish national advertising prevalence, factual truth, persuasion, "
        "audience reach or the parties' private intentions. Speaker quotation, extraction "
        "quality, primary attacks and positive self-description still require context."
    )
    paragraph(
        f"The final eligibility cutoff remains {END}, inclusive. The current snapshot "
        f"stops at {dataset['until']}; uncollected future dates are not zeros. Research "
        "refreshes may update the saved evidence, figures and both drafts, but website "
        "and Substack publication remain on hold."
    )
    return {
        "version": "article-1",
        "snapshot_id": dataset["snapshot_id"],
        "publication_status": "draft_not_published",
        "until": dataset["until"],
        "title": "How Democrats and Republicans talk in their 2026 ads",
        "subtitle": "Issue language, opponent portrayals and the limits of an uneven collection.",
        "blocks": blocks,
        "context_illustrations": illustrations,
        "opponent_examples": examples,
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
            "[Complete local analysis (JSON)](analysis.json) | "
            "[Technical report](analysis.html) | [All chart data](figures/chart-data.json) | "
            "[Descriptor contexts](figures/descriptor-evidence.json)",
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
        "<a href='figures/descriptor-evidence.json'>Descriptor contexts</a></p>"
        "</main><footer>Research draft. No website or Substack publication has occurred."
        "</footer></body></html>"
    )
