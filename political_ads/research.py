from __future__ import annotations

from hashlib import sha256
from html import escape
from pathlib import Path

from political_ads.analysis import stratified_comparisons
from political_ads.cli import read_json, write_json
from political_ads.editorial import article_data, margin_html, substack_markdown
from political_ads.figures import build_figures
from political_ads.portrayals import portrayal_summary
from political_ads.publication import csv_export, prepare, report, validate_dataset


def research(root: Path, dataset: dict | None = None) -> dict:
    dataset = prepare(root) if dataset is None else dataset
    validate_dataset(dataset)
    strata = stratified_comparisons(dataset["ads"], dataset["codebook"])
    portrayals = portrayal_summary(dataset["ads"], dataset["portrayal_codebook"])
    figures = build_figures(dataset, strata, portrayals, root / "outputs/figures")
    article = article_data(dataset, strata, portrayals, figures)
    result = {
        "analysis_version": "person-portrayals-1",
        "publication_status": "local_only",
        "monthly_basis": "Earliest publisher release/post, in-scope Google delivery or "
        "Snap scheduled start of each exact party/message; pre-2026 carryovers anchored "
        "to January, not new launches",
        "stratum_basis": "Exact party/messages deduplicated after each non-temporal filter",
        "dataset": dataset,
        "comparisons": strata,
        "person_portrayals": portrayals,
        "figures": figures,
        "chart_data_hash": sha256(
            (root / "outputs/figures/chart-data.json").read_bytes()
        ).hexdigest(),
        "article": article,
    }
    output = root / "outputs"
    write_json(output / "analysis.json", result)
    (output / "analysis-ads.csv").write_text(csv_export(dataset["ads"]), newline="")
    (output / "analysis.html").write_text(research_report(dataset, strata, portrayals, figures))
    write_json(output / "article-data.json", article)
    (output / "substack.md").write_text(substack_markdown(article))
    (output / "themarginoferror.html").write_text(margin_html(article))
    return result


def validate_research(root: Path, dataset: dict) -> None:
    output = root / "outputs"
    result = read_json(output / "analysis.json", {})
    if result.get("dataset") != dataset:
        raise ValueError("Research evidence does not match the built corpus")
    strata = stratified_comparisons(dataset["ads"], dataset["codebook"])
    if result["comparisons"] != strata:
        raise ValueError("Research metrics do not reconcile to the corpus")
    portrayals = portrayal_summary(dataset["ads"], dataset["portrayal_codebook"])
    if result["person_portrayals"] != portrayals:
        raise ValueError("Research portrayal evidence does not reconcile to the corpus")
    manifest = result["figures"]
    if (
        manifest["snapshot_id"] != dataset["snapshot_id"]
        or manifest["until"] != dataset["until"]
        or manifest["publication_status"] != "local_only"
    ):
        raise ValueError("Figure snapshot does not match the corpus")
    for folder in (output / "figures", root / "web/public/figures"):
        if read_json(folder / "manifest.json", {}) != manifest:
            raise ValueError(f"Figure manifest does not match research: {folder}")
        data_file = folder / "chart-data.json"
        if (
            not data_file.exists()
            or sha256(data_file.read_bytes()).hexdigest() != result["chart_data_hash"]
        ):
            raise ValueError(f"Chart data hash does not match research: {folder}")
        if read_json(folder / "portrayal-evidence.json", {}) != portrayals:
            raise ValueError(f"Figure portrayal evidence does not match research: {folder}")
        for chart in manifest["charts"]:
            for kind in ("png", "csv"):
                asset = folder / chart[kind]
                if (
                    not asset.exists()
                    or sha256(asset.read_bytes()).hexdigest() != chart["sha256"][kind]
                ):
                    raise ValueError(f"Figure asset hash does not match research: {asset}")
    article = article_data(dataset, strata, portrayals, manifest)
    if result["article"] != article or read_json(output / "article-data.json", {}) != article:
        raise ValueError("Article findings do not reconcile to research")
    for path, expected in (
        (output / "substack.md", substack_markdown(article)),
        (output / "themarginoferror.html", margin_html(article)),
        (root / "web/public/article.html", margin_html(article, web=True)),
        (output / "analysis.html", research_report(dataset, strata, portrayals, manifest)),
        (
            root / "web/public/report.html",
            research_report(dataset, strata, portrayals, manifest, web=True),
        ),
    ):
        if not path.exists() or path.read_text() != expected:
            raise ValueError(f"Research draft or report does not match its evidence: {path}")


def research_report(
    dataset: dict, strata: dict, portrayals: dict, figures: dict | None = None, *, web: bool = False
) -> str:
    def ratio(value):
        return (
            f"{value['count']:,}/{value['total']:,} ({value['share']:.1%})"
            if value["total"]
            else "No eligible messages"
        )

    def table(headers, rows):
        return (
            "<table><thead><tr>"
            + "".join(f"<th>{escape(str(value))}</th>" for value in headers)
            + "</tr></thead><tbody>"
            + "".join(
                "<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in row) + "</tr>"
                for row in rows
            )
            + "</tbody></table>"
        )

    sections = [
        "<h2>Descriptions of people, not words near names</h2>",
        f"<p>{escape(portrayals['method'])}</p>",
        f"<p>{escape(portrayals['denominator'])}</p>",
        "<h3>Review coverage</h3>",
        table(
            ("Advertiser", "Reviewed", "Uncertain", "Unreviewed", "Stale"),
            [
                (
                    party,
                    *(
                        ratio(portrayals["coverage"][party][status])
                        for status in ("reviewed", "uncertain", "unreviewed", "stale")
                    ),
                )
                for party in ("D", "R")
            ],
        ),
        "<p>Completion is not accuracy. There is no independent held-out human evaluation. "
        "Future refreshes can add unreviewed messages; their absence from these rates "
        "must not be interpreted as neutral or non-attacking advertising.</p>",
    ]
    for scope, title in (
        ("opponents", "How each party describes opposing-party people"),
        ("self", "How advertisers describe their own or supported candidates"),
        ("same_party_opponents", "Same-party rivals, kept separate"),
        ("collective_opponents", "Opposing-party collectives, kept separate from people"),
    ):
        groups = portrayals["scopes"][scope]
        sections.extend(
            [
                f"<h2>{title}</h2>",
                table(
                    (
                        "Advertiser",
                        "With this description / reviewed",
                        "No such description / reviewed",
                    ),
                    [
                        (
                            party,
                            ratio(groups[party]["described"]),
                            ratio(groups[party]["no_description"]),
                        )
                        for party in ("D", "R")
                    ],
                ),
                table(
                    ("Portrayal of target", "Democratic ads", "Republican ads"),
                    [
                        (
                            tone.replace("_", " ").capitalize(),
                            *(ratio(groups[p]["tones"][tone]) for p in ("D", "R")),
                        )
                        for tone in ("negative_only", "positive_only", "mixed", "neutral_only")
                    ],
                ),
                "<p>Exclusive categories above sum to 100% among messages with a description. "
                "The following inclusive percentages both include mixed messages and can "
                "therefore sum to more than 100%.</p>",
                table(
                    ("Includes this tone", "Democratic ads", "Republican ads"),
                    [
                        (
                            tone.capitalize(),
                            *(ratio(groups[p]["inclusive_tones"][tone]) for p in ("D", "R")),
                        )
                        for tone in ("negative", "positive")
                    ],
                ),
            ]
        )
        if scope in ("opponents", "self"):
            sections.append(
                table(
                    ("How the person is framed", "Democratic ads", "Republican ads"),
                    [
                        (label, *(ratio(groups[p]["frames"][frame]) for p in ("D", "R")))
                        for frame, label in sorted(dataset["portrayal_codebook"]["frames"].items())
                    ],
                )
            )
    sections.extend(
        [
            "<h2>Does the portrayal comparison survive a source-mix check?</h2>",
            "<p>Exclude each party's largest publisher by source-record count, then deduplicate "
            "after exclusion. This is a stress test, not a population correction. Excluded: "
            + escape(
                "; ".join(
                    f"{p}: {name}"
                    for p, name in portrayals["sensitivity"]["excluded_publishers"].items()
                )
            )
            + ".</p>",
            table(
                (
                    "Scope",
                    "Advertiser",
                    "Negative incl. mixed: all",
                    "Excluding largest",
                    "Positive incl. mixed: all",
                    "Excluding largest",
                ),
                [
                    (
                        scope,
                        party,
                        ratio(portrayals["scopes"][scope][party]["inclusive_tones"]["negative"]),
                        ratio(
                            portrayals["sensitivity"]["scopes"][scope][party]["inclusive_tones"][
                                "negative"
                            ]
                        ),
                        ratio(portrayals["scopes"][scope][party]["inclusive_tones"]["positive"]),
                        ratio(
                            portrayals["sensitivity"]["scopes"][scope][party]["inclusive_tones"][
                                "positive"
                            ]
                        ),
                    )
                    for scope in ("opponents", "self")
                    for party in ("D", "R")
                ],
            ),
            "<details><summary>Read the context-coded portrayal evidence</summary>"
            "<p>Full literal passages, target anchors, voice, offsets and input hashes are in "
            "<a href='figures/portrayal-evidence.json'>the portrayal ledger download</a>. "
            "Uncertain and non-endorsed descriptions are retained here "
            "but excluded from metrics.</p>",
            table(
                (
                    "Ad",
                    "Advertiser",
                    "Target",
                    "Party / role",
                    "Tone / voice",
                    "Frame",
                    "Exact passage",
                ),
                [
                    (
                        hit["ad_id"],
                        hit["party"],
                        hit["target"],
                        hit["target_party"] + " / " + hit["target_role"],
                        hit["tone"] + " / " + hit["voice"],
                        dataset["portrayal_codebook"]["frames"][hit["frame"]],
                        hit["quote"],
                    )
                    for hit in portrayals["evidence"]
                ],
            ),
            "</details>",
        ]
    )
    if figures:
        sections.append(
            "<h2>PNG figures and exact chart data</h2>"
            "<p>Full-snapshot figures do not change with dashboard filters. All include "
            "counts, denominators and included ad IDs in their CSV and "
            "<a href='figures/chart-data.json'>combined JSON</a>.</p>"
            + "".join(
                f"<figure><h3>{escape(chart['title'])}</h3>"
                f"<a href='figures/{escape(chart['png'])}'><img loading='lazy' "
                f"src='figures/{escape(chart['png'])}' "
                f"alt='{escape(chart['description'], quote=True)}'></a>"
                f"<figcaption>{escape(chart['description'])} "
                f"<a href='figures/{escape(chart['csv'])}'>Exact CSV</a>"
                "</figcaption></figure>"
                for chart in figures["charts"]
            )
        )
    sections.extend(
        [
            "<h2>Historical coverage</h2>"
            "<p>First observed exact messages, not airings or spending. Snap dates are scheduled "
            "intervals; publisher posts are not verified paid delivery. Pre-2026 carryovers "
            "start in January, not as new launches. Early and final months are partial. "
            "Changed-target templates are distinct messages, not independent strategies.</p>",
            table(
                ("Month", "D messages", "R messages", "D publishers", "R publishers"),
                [
                    (
                        month,
                        group["coverage"]["D"]["messages"],
                        group["coverage"]["R"]["messages"],
                        len(group["coverage"]["D"]["publishers"]),
                        len(group["coverage"]["R"]["publishers"]),
                    )
                    for month, group in strata["month"].items()
                ],
            ),
            "<h2>Comparison boundaries</h2>"
            "<p>Unequal races, publishers, primary/general phases and extraction formats limit "
            "party comparisons. Unknown identities and phases remain unknown. ASR/OCR can "
            "misrecognize words and negation. Claims about people describe advertiser framing, "
            "not factual truth, persuasion, reach or national party strategy. The November 4 "
            "inclusive cutoff and research-only publication hold remain in force.</p>",
            table(
                ("Dimension", "Stratum", "D messages", "R messages"),
                [
                    (
                        field,
                        name,
                        group["coverage"]["D"]["messages"],
                        group["coverage"]["R"]["messages"],
                    )
                    for field in ("chamber", "sponsor_type", "phase", "placement", "record_format")
                    for name, group in strata[field].items()
                ],
            ),
        ]
    )
    content = (
        report(dataset)
        .replace(
            "<h2>A closer Senate comparison</h2>",
            "".join(sections) + "<h2>Secondary issue-language context</h2>"
            "<h2>A closer Senate comparison</h2>",
        )
        .replace(
            "</head>",
            "<style>figure{margin:2rem 0}table{display:block;max-width:100%;overflow-x:auto}"
            "td{overflow-wrap:anywhere}figcaption{font-size:.85rem;color:#666}"
            "img{width:100%;height:auto}summary{cursor:pointer}</style></head>",
        )
    )
    return (
        content.replace("data/ads.csv", "data/ads.csv" if web else "analysis-ads.csv")
        .replace("data/dataset.json", "data/dataset.json" if web else "analysis.json")
        .replace(
            "<a href='./'>The Margin of Error / Political ads</a>",
            "<p><strong>LOCAL ONLY - website publication is on hold.</strong></p>",
        )
        .replace(
            "<link rel='canonical' href='https://www.themarginoferror.com/political-ads/report.html'>",
            "",
        )
    )
