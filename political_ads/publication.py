from __future__ import annotations

import csv
import gzip
import html
import io
import json
import re
import shutil
from pathlib import Path

from political_ads.analysis import (
    annotate,
    apply_reviews,
    comparison,
    distinctive_phrases,
    publisher,
    timeline,
    unique_messages,
)
from political_ads.cli import load_corpus, read_json, write_json
from political_ads.portrayals import apply_portrayal_reviews, validate_portrayal_review
from political_ads.registry import enrich
from political_ads.schema import Ad, digest, eligible

METHODOLOGY = [
    "This is an observed corpus of official ad releases, reviewed campaign originals, "
    "Google previews and native Snap creatives, not a census of all ads aired.",
    "Dates distinguish publisher releases/posts, Google-reported delivery and "
    "Snap scheduled intervals. "
    "Snap's positive impressions do not independently locate delivery within its scheduled dates.",
    "Party alignment describes the source publisher; "
    "joint creative payers require separate review.",
    "Reviewed publisher alignment uses documented electoral programs and FEC support/oppose "
    "filings, not a blank formal party field. Democratic-leaning can include cross-party "
    "endorsements; documented bipartisan programs stay separate. Per-record hash-bound "
    "reviews retain original classifications and do not rewrite text or extraction evidence.",
    "Unresolved and other publisher alignments remain in the evidence explorer and downloads "
    "but do not enter Democratic/Republican comparison denominators.",
    "Charts count unique exact messages per party after filters, "
    "not placements, spending or reach.",
    "Issue charts show exact phrase-family matches, not validated semantic topic classifications.",
    "Matched language may be quoted, denied, or used positively. "
    "It is not an attack classification.",
    "Opponent examples are editorially context-checked excerpts, not representative estimates.",
    "Party/chamber/source composition differs. "
    "Use Senate or within-race filters for closer comparisons.",
    "Unknown election phase and race remain unknown "
    "rather than inferred solely from calendar dates.",
    "Ads make claims. This project does not establish their truth or measure persuasion.",
    "Automatic video captions may misrecognize words or names. "
    "On-screen-only claims are not yet included in caption-only records.",
    "Reviewed campaign originals retain exact publisher post timestamps and media hashes. "
    "A post date is not verified first release or paid delivery; undated recovered originals "
    "stay outside dated comparisons. Local speech recognition may misrecognize names or negation.",
    "Publisher-quoted ad copy is separately flagged: it may omit parts of the creative. "
    "Press commentary and biographies are excluded.",
    "Reviewed standalone image ads use local OCR with image hashes, line coordinates, "
    "and explicit word/reading-order uncertainty; video thumbnails are excluded.",
    "Google native image/search previews are joined by exact public FEC committee IDs. "
    "Each preview stays separate; parent-creative delivery does not prove each variant served.",
    "Google previews include fundraising and payer/platform boilerplate and may truncate text. "
    "Compare formats separately; their prevalence is not a party-strategy finding.",
    "Temporal charts anchor pre-2026 Google carryovers to January's first in-scope date, "
    "not a new launch. First/last delivery intervals do not establish continuous delivery.",
    "Snap payers use exact FEC IDs, exact FEC legal names or explicitly reviewed name crosswalks. "
    "Repeated platform ad IDs sharing a payer and asset form one creative record.",
    "Native Snap videos use local multilingual Whisper speech recognition and one-second "
    "frame OCR. Words, names and short overlays may be missed or misrecognized; none is "
    "a certified transcript.",
    "Speech and novel on-screen lines are separate evidence lanes. Repeated speech/subtitles are "
    "deduplicated, low-confidence OCR is retained outside analyzed text, and phrase matches "
    "cannot cross from speech into an overlay or between independent overlay lines.",
    "Person-portrayal analysis uses saved AI-assisted full-text contextual reviews, not "
    "nearby adjectives or a sentiment lexicon. Targets, supported candidates, same-party "
    "rivals, collectives, quoted opponents and rebutted claims remain distinct. Labels "
    "describe attributed portrayals, not claim truth; they are not independent human gold.",
    "Tone shares use reviewed exact messages with an endorsed description in the named "
    "scope. Negative-only, positive-only, mixed and neutral-only are exclusive; no "
    "description is not neutral. Frames overlap. Uncertain, stale and unreviewed "
    "messages are disclosed and excluded rather than silently classified.",
]


def spreadsheet_cell(value):
    if isinstance(value, str) and re.match(r"^[\s]*[=+\-@]", value):
        return "'" + value
    return value


def csv_export(ads: list[dict]) -> str:
    stream = io.StringIO(newline="")
    keys = [
        "id",
        "message_id",
        "alignment",
        "sponsor",
        "sponsor_type",
        "source",
        "source_url",
        "published",
        "date_basis",
        "delivery_start",
        "delivery_end",
        "placement",
        "phase",
        "race",
        "state",
        "chamber",
        "language",
        "title",
        "text",
        "source_hash",
        "text_hash",
        "attribution_basis",
        "segments",
        "issues",
        "portrayal_markers",
    ]
    keys = list(dict.fromkeys([*keys, *(key for ad in ads for key in ad)]))
    writer = csv.DictWriter(stream, fieldnames=keys, extrasaction="ignore")
    writer.writeheader()
    for ad in ads:
        row = {
            key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
            for key, value in ad.items()
        }
        # Spreadsheet export must not turn source-controlled text into formulas.
        writer.writerow({key: spreadsheet_cell(value) for key, value in row.items()})
    return stream.getvalue()


def report(dataset: dict) -> str:
    esc = html.escape
    publishers = {publisher(ad) for ad in dataset["ads"]}
    items = []
    for party, name in (("D", "Democratic"), ("R", "Republican")):
        scope = [ad for ad in dataset["ads"] if ad["alignment"] == party]
        items.append(
            f"<h2>{name} publishers</h2><p>{len(scope)} source records; "
            f"{len(unique_messages(scope))} exact unique messages.</p>"
        )
        for example in [e for e in dataset["examples"] if e["party"] == party]:
            items.append(
                f"<h3>{esc(example['frame'])}: {esc(example['target'])}</h3>"
                f"<blockquote>{esc(example['quote'])}</blockquote>"
                f"<p>{esc(example['context'])}</p>"
                f"<p><a href='{esc(example['source_url'], quote=True)}'>Original release</a></p>"
            )
    issue_rows = "".join(
        "<tr><th>"
        + esc(row["label"])
        + "</th>"
        + "".join(f"<td>{row[p]['count']} / {row[p]['total']}</td>" for p in ("D", "R"))
        + "</tr>"
        for row in dataset["issues"]
    )
    methods = "".join(f"<li>{esc(method)}</li>" for method in METHODOLOGY)
    senate = [ad for ad in dataset["ads"] if ad["chamber"] == "Senate"]
    senate_issues = comparison(senate, list(dataset["codebook"]["issues"]))
    findings = []
    for party, name in (("D", "Democratic"), ("R", "Republican")):
        top = sorted(senate_issues, key=lambda row: (-row[party]["count"], row["label"]))[:3]
        observed = [
            f"{esc(row['label'].lower())} ({row[party]['count']}/{row[party]['total']})"
            for row in top
            if row[party]["count"]
        ]
        if observed:
            findings.append(
                f"<p>Among {name} Senate messages, the most frequently matched issue families "
                f"were {', '.join(observed)}. These are transcript-level phrase counts, not "
                "validated estimates of an ad's main subject.</p>"
            )
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>The language of political ads — report</title>"
        "<meta name='description' content='Compare 2026 federal ad language, "
        "with contextual opponent portrayals and complete source transcripts.'>"
        "<link rel='canonical' href='https://www.themarginoferror.com/political-ads/report.html'>"
        "<style>body{max-width:760px;margin:3rem auto;padding:0 1rem;color:#232722;"
        "font:18px/1.65 Georgia,serif}a{color:#28526d}h1{line-height:1.1;font-size:3rem}"
        "blockquote{border-left:3px solid #a9b5ac;margin-left:0;padding-left:1.5rem}"
        "table{width:100%;border-collapse:collapse;font:15px/1.6 system-ui}"
        "th,td{text-align:left;border-bottom:1px solid #ddd;padding:.6rem}"
        "@media print{body{margin:0;max-width:none}}</style></head><body>"
        "<a href='./'>The Margin of Error / Political ads</a>"
        "<h1>The language of political ads</h1>"
        f"<p>2026 federal elections · observed records through {esc(dataset['until'])}</p>"
        f"<p>{len(dataset['ads'])} English ad-text records from "
        f"{len(publishers)} publishers.</p>"
        "<p>This initial report describes language in an observed collection. Its strongest "
        "evidence is the ads themselves; the examples below are not national prevalence estimates."
        "</p><h2>A closer Senate comparison</h2>"
        + "".join(findings)
        + "<p>Even within a chamber, publishers, races, dates and extraction methods differ. "
        "These differences must not be treated as a pure effect of party.</p>"
        "<h2>Language associated with issues</h2><p>Exact phrase matches per unique message. "
        "An ad can match several families. A quotation is still a lexical match.</p>"
        "<table><thead><tr><th>Phrase family</th><th>Democratic</th><th>Republican</th>"
        f"</tr></thead><tbody>{issue_rows}</tbody></table>"
        + "".join(items)
        + f"<h2>How to read this report</h2><ul>{methods}</ul>"
        "<p><a href='data/ads.csv'>Download the complete text and evidence (CSV)</a> · "
        "<a href='data/dataset.json'>Download JSON</a></p></body></html>"
    )


def prepare(root: Path) -> dict:
    corpus = load_corpus(root)
    if not corpus or not corpus["ads"]:
        raise ValueError("Publication requires actual collected text")
    registry = read_json(root / "data/site/candidates.json", {"candidates": []})
    codebook = read_json(root / "data/codebook.json", None)
    ledger = read_json(root / "data/reviews.json", {"examples": []})
    ads = [
        enrich(ad, registry["candidates"]) for ad in corpus["ads"] if eligible(ad, corpus["until"])
    ]
    ads = annotate(sorted(ads, key=lambda ad: (ad["published"], ad["id"])), codebook)
    portrayal_codebook = read_json(
        root / "data/portrayal-codebook.json",
        {
            "version": "person-portrayals-1",
            "method": "No contextual reviews loaded",
            "frames": {},
            "voices": [
                "advertiser",
                "adopted_clip",
                "quoted_opponent",
                "rebutted_claim",
                "unclear",
            ],
        },
    )
    ads = apply_portrayal_reviews(
        ads, read_json(root / "data/portrayal-reviews.json", {}), portrayal_codebook
    )
    examples = apply_reviews(ads, ledger)
    dataset = {
        "schema_version": "1",
        "analysis_version": codebook["version"],
        "until": corpus["until"],
        "latest_release": max(ad["published"] for ad in ads),
        "first_release": min(ad["published"] for ad in ads),
        "ads": ads,
        "sources": corpus["sources"],
        "examples": examples,
        "issues": comparison(ads, list(codebook["issues"])),
        "portrayals": comparison(
            ads,
            list(codebook["portrayal_language"]),
            "portrayal_markers",
        ),
        "distinctive": distinctive_phrases(ads),
        "timeline": timeline(ads),
        "methodology": METHODOLOGY,
        "codebook": codebook,
        "portrayal_codebook": portrayal_codebook,
        "validation": {
            "reviewed_examples": len(examples),
            "semantic_classifier": "saved AI-assisted contextual reviews; coverage disclosed; "
            "no independent held-out human accuracy evaluation",
            "extraction": "publisher transcripts, flagged publisher-quoted ad copy, "
            "public English captions, reviewed image ads, Google preview OCR and native "
            "Snap and reviewed campaign-original speech/frame extraction; "
            "language detector excludes non-English/uncertain",
            "independent_human_gold": False,
        },
    }
    dataset["snapshot_id"] = publication_hash(dataset)
    return dataset


def publication_hash(dataset: dict) -> str:
    payload = {key: value for key, value in dataset.items() if key != "snapshot_id"}
    return digest(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def validate_dataset(dataset: dict) -> None:
    seen = set()
    for ad in dataset["ads"]:
        if ad["id"] in seen:
            raise ValueError(f"Duplicate source identity: {ad['id']}")
        seen.add(ad["id"])
        Ad(**{key: value for key, value in ad.items() if key in Ad.__dataclass_fields__}).validate()
        if review := ad.get("alignment_review"):
            if (
                review["alignment"] != ad["alignment"]
                or review["reviewed_source_hash"] != ad["source_hash"]
                or review["source"] != ad["source"]
                or review["sponsor"] != ad["sponsor"]
                or review["expected_alignment"] != ad["original_alignment"]
            ):
                raise ValueError(f"Publisher alignment review mismatch: {ad['id']}")
        if not eligible(ad, dataset["until"]):
            raise ValueError(f"Out-of-scope ad: {ad['id']}")
        if ad["text_hash"] != digest(ad["text"]):
            raise ValueError("Original text hash mismatch")
        validate_portrayal_review(ad, dataset["portrayal_codebook"])
        for evidence in ad["issues"] + ad["portrayal_markers"]:
            if ad["text"][evidence["start"] : evidence["end"]] != evidence["text"]:
                raise ValueError(f"Broken text evidence offsets: {ad['id']}")
    expected = comparison(dataset["ads"], list(dataset["codebook"]["issues"]))
    if expected != dataset["issues"]:
        raise ValueError("Published issue metrics do not reconcile to source ads")
    if not dataset["examples"]:
        raise ValueError("Opponent comparison requires source-checked examples")
    if (
        comparison(
            dataset["ads"], list(dataset["codebook"]["portrayal_language"]), "portrayal_markers"
        )
        != dataset["portrayals"]
    ):
        raise ValueError("Published vocabulary metrics do not reconcile to source ads")
    by_id = {ad["id"]: ad for ad in dataset["ads"]}
    for example in dataset["examples"]:
        ad = by_id[example["ad_id"]]
        if ad["text"][example["start"] : example["end"]] != example["quote"]:
            raise ValueError("Broken reviewed excerpt offsets")
        if ad["source_hash"] != example["source_hash"]:
            raise ValueError("Broken reviewed source hash")
    if dataset["snapshot_id"] != publication_hash(dataset):
        raise ValueError("Publication snapshot hash mismatch")


def preview(dataset: dict) -> str:
    esc = html.escape
    rows = sorted(dataset["issues"], key=lambda row: -(row["D"]["count"] + row["R"]["count"]))[:3]
    bars = []
    for index, row in enumerate(rows):
        y = 320 + index * 70
        bars.append(f'<text x="70" y="{y + 16}" font-size="20">{esc(row["label"])}</text>')
        for offset, party, color in ((0, "D", "#426a8d"), (21, "R", "#a65c4e")):
            width = round((row[party]["share"] or 0) * 530)
            bars.append(
                f'<rect x="520" y="{y + offset}" width="530" height="10" fill="#e5e8df"/>'
                f'<rect x="520" y="{y + offset}" width="{width}" height="10" fill="{color}"/>'
            )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">'
        '<rect width="1200" height="630" fill="#f7f6f2"/>'
        '<g fill="#28352f" font-family="Georgia,serif">'
        '<text x="70" y="70" font-size="18">THE MARGIN OF ERROR / 2026 MIDTERMS</text>'
        '<text x="70" y="170" font-size="62">The language of political ads.</text>'
        f'<text x="70" y="225" font-size="24">{len(dataset["ads"])} ad transcripts. '
        "The words behind the comparison.</text>"
        '<text x="520" y="285" fill="#426a8d" font-size="17">Democratic</text>'
        '<text x="680" y="285" fill="#a65c4e" font-size="17">Republican</text>'
        + "".join(bars)
        + '<text x="70" y="570" font-size="16">Observed official releases, not all ads aired. '
        "Phrase-family matches per unique message.</text></g></svg>"
    )


def build(root: Path) -> None:
    from political_ads.editorial import margin_html
    from political_ads.figures import remove_retired_figures
    from political_ads.research import research, research_report, validate_research

    dataset = prepare(root)
    validate_dataset(dataset)
    staging = root / "web/public/data.next"
    staging.mkdir(parents=True, exist_ok=True)
    write_json(staging / "dataset.json", dataset)
    (staging / "ads.csv").write_text(csv_export(dataset["ads"]))
    (staging / "dataset.json.gz").write_bytes(
        gzip.compress((staging / "dataset.json").read_bytes(), mtime=0)
    )
    target = root / "web/public/data"
    target.mkdir(parents=True, exist_ok=True)
    for file in staging.iterdir():
        file.replace(target / file.name)
    staging.rmdir()
    analysis = research(root, dataset)
    shutil.copytree(root / "outputs/figures", root / "web/public/figures", dirs_exist_ok=True)
    remove_retired_figures(root / "web/public/figures")
    (root / "web/public/article.html").write_text(margin_html(analysis["article"], web=True))
    (root / "web/public/report.html").write_text(
        research_report(
            dataset,
            analysis["comparisons"],
            analysis["person_portrayals"],
            analysis["figures"],
            web=True,
        )
    )
    (root / "web/public/preview.svg").write_text(preview(dataset))
    validate_research(root, dataset)
    write_json(
        root / "outputs/validation.json",
        {
            "snapshot_id": dataset["snapshot_id"],
            "records": len(dataset["ads"]),
            "checks": [
                "unique IDs",
                "schema",
                "scope",
                "source hashes",
                "evidence offsets",
                "metric reconciliation",
                "reviewed quote hashes",
                "research metric reconciliation",
                "figure and chart-data hashes",
                "matching unpublished article editions",
            ],
            **dataset["validation"],
        },
    )
    print(f"Built snapshot {dataset['snapshot_id'][:12]}: {len(dataset['ads'])} real ads")


def validate(root: Path) -> None:
    dataset = read_json(root / "web/public/data/dataset.json", None)
    if dataset is None:
        raise ValueError("No built dataset; run build first")
    validate_dataset(dataset)
    with (root / "web/public/data/ads.csv").open(newline="") as stream:
        csv_text = stream.read()
    csv.field_size_limit(max(csv.field_size_limit(), len(csv_text)))
    csv_data = list(csv.DictReader(io.StringIO(csv_text)))
    if len(csv_data) != len(dataset["ads"]) or any(not row["text"] for row in csv_data):
        raise ValueError("Text downloads are incomplete")
    for record, ad in zip(csv_data, dataset["ads"], strict=True):
        for key, value in ad.items():
            if isinstance(value, (list, dict)):
                matches = key in record and json.loads(record[key]) == value
            else:
                expected = spreadsheet_cell(value)
                matches = record.get(key) == ("" if expected is None else str(expected))
            if not matches:
                raise ValueError(f"Evidence downloads do not match the corpus: {ad['id']} / {key}")
    compressed = root / "web/public/data/dataset.json.gz"
    if json.loads(gzip.decompress(compressed.read_bytes())) != dataset:
        raise ValueError("Compressed evidence download does not match the corpus")
    from political_ads.research import validate_research

    validate_research(root, dataset)
    print(f"Verified {len(csv_data)} text-complete records and evidence-linked metrics")
