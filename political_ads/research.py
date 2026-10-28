from __future__ import annotations

from collections import Counter
from hashlib import sha256
from html import escape
from pathlib import Path

from political_ads.analysis import stratified_comparisons
from political_ads.cli import read_json, write_json
from political_ads.descriptors import descriptive_language
from political_ads.editorial import article_data, margin_html, substack_markdown
from political_ads.figures import build_figures
from political_ads.publication import csv_export, prepare, report, validate_dataset


def descriptor_aliases(root: Path) -> list[dict]:
    candidates = {
        candidate["candidate_id"]: candidate
        for candidate in read_json(root / "data/site/candidates.json", {"candidates": []})[
            "candidates"
        ]
    }
    return [
        candidates[alias["candidate_id"]] | {"reviewed_alias": alias}
        for alias in read_json(root / "data/snap-candidate-aliases.json", [])
        if alias["candidate_id"] in candidates
    ]


def research(root: Path, dataset: dict | None = None) -> dict:
    dataset = prepare(root) if dataset is None else dataset
    validate_dataset(dataset)
    strata = stratified_comparisons(dataset["ads"], dataset["codebook"])
    descriptors = descriptive_language(dataset, descriptor_aliases(root))
    figures = build_figures(dataset, strata, descriptors, root / "outputs/figures")
    article = article_data(
        dataset,
        strata,
        descriptors,
        figures,
        read_json(root / "data/descriptor-context-reviews.json", {}),
    )
    result = {
        "analysis_version": "stratified-2",
        "publication_status": "local_only",
        "monthly_basis": "Earliest publisher release/post, in-scope Google delivery or "
        "Snap scheduled start of each exact party/message; pre-2026 carryovers anchored "
        "to January, not new launches",
        "stratum_basis": "Exact party/messages deduplicated after each non-temporal filter",
        "dataset": dataset,
        "comparisons": strata,
        "descriptive_language": descriptors,
        "figures": figures,
        "chart_data_hash": sha256(
            (root / "outputs/figures/chart-data.json").read_bytes()
        ).hexdigest(),
        "article": article,
    }
    output = root / "outputs"
    write_json(output / "analysis.json", result)
    (output / "analysis-ads.csv").write_text(csv_export(dataset["ads"]), newline="")
    (output / "analysis.html").write_text(research_report(dataset, strata, descriptors, figures))
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
    descriptors = descriptive_language(dataset, descriptor_aliases(root))
    if result["descriptive_language"] != descriptors:
        raise ValueError("Research descriptor evidence does not reconcile to the corpus")
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
        if read_json(folder / "descriptor-evidence.json", {}) != descriptors:
            raise ValueError(f"Figure descriptor evidence does not match research: {folder}")
        for chart in manifest["charts"]:
            for kind in ("png", "csv"):
                asset = folder / chart[kind]
                if (
                    not asset.exists()
                    or sha256(asset.read_bytes()).hexdigest() != chart["sha256"][kind]
                ):
                    raise ValueError(f"Figure asset hash does not match research: {asset}")
    article = article_data(
        dataset,
        strata,
        descriptors,
        manifest,
        read_json(root / "data/descriptor-context-reviews.json", {}),
    )
    if result["article"] != article or read_json(output / "article-data.json", {}) != article:
        raise ValueError("Article findings do not reconcile to research")
    for path, expected in (
        (output / "substack.md", substack_markdown(article)),
        (output / "themarginoferror.html", margin_html(article)),
        (root / "web/public/article.html", margin_html(article, web=True)),
        (output / "analysis.html", research_report(dataset, strata, descriptors, manifest)),
        (
            root / "web/public/report.html",
            research_report(dataset, strata, descriptors, manifest, web=True),
        ),
    ):
        if not path.exists() or path.read_text() != expected:
            raise ValueError(f"Research draft or report does not match its evidence: {path}")


def research_report(
    dataset: dict,
    strata: dict,
    descriptors: dict | None = None,
    figures: dict | None = None,
    *,
    web: bool = False,
) -> str:
    def ratio(row, party):
        value = row[party]
        if not value["total"]:
            return "No messages"
        return f"{value['count']}/{value['total']} ({value['share']:.1%})"

    def table(headers, rows):
        head = "".join(f"<th>{escape(str(value))}</th>" for value in headers)
        body = "".join(
            "<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in row) + "</tr>"
            for row in rows
        )
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

    monthly = []
    for month, group in strata["month"].items():
        d, r = group["coverage"]["D"], group["coverage"]["R"]
        monthly.append(
            (month, d["messages"], r["messages"], len(d["publishers"]), len(r["publishers"]))
        )
    coverage = []
    for source, group in strata["source"].items():
        for party in ("D", "R"):
            scope = group["coverage"][party]
            if scope["records"]:
                coverage.append((source, party, scope["records"], scope["messages"]))
    vocab = [
        (row["label"], ratio(row, "D"), ratio(row, "R")) for row in strata["overall"]["portrayals"]
    ]
    markers = {row["label"]: row for row in strata["overall"]["portrayals"]}
    sensitivity = strata["sensitivity"]
    excluded = ", ".join(
        f"{party}: {source}" for party, source in sensitivity["excluded_publishers"].items()
    )
    sensitivity_rows = []
    reduced_issues = {
        row["label"]: row for row in sensitivity["without_largest_publisher_per_party"]["issues"]
    }
    for row in strata["overall"]["issues"]:
        reduced = reduced_issues[row["label"]]
        sensitivity_rows.append(
            (
                row["label"],
                ratio(row, "D"),
                ratio(reduced, "D"),
                ratio(row, "R"),
                ratio(reduced, "R"),
            )
        )
    monthly_issues = []
    for month, group in strata["month"].items():
        for row in group["issues"]:
            monthly_issues.append((month, row["label"], ratio(row, "D"), ratio(row, "R")))
    subgroup_rows = []
    for field in ("chamber", "sponsor_type", "phase", "placement", "record_format"):
        for value, group in strata[field].items():
            subgroup_rows.append(
                (
                    field,
                    value,
                    group["coverage"]["D"]["messages"],
                    group["coverage"]["R"]["messages"],
                )
            )
    race_rows = [
        (race, group["coverage"]["D"]["messages"], group["coverage"]["R"]["messages"])
        for race, group in strata["race"].items()
        if race != "Unresolved"
        and all(group["coverage"][party]["messages"] for party in ("D", "R"))
    ]
    reviewed = [ad for ad in dataset["ads"] if ad.get("alignment_review")]
    alignment_counts = Counter(
        (ad["alignment_review"]["id"], ad["source"], ad["sponsor"], ad["alignment"])
        for ad in reviewed
    )
    reviews = {ad["alignment_review"]["id"]: ad["alignment_review"] for ad in reviewed}
    alignment_rows = [
        (sponsor, source, party, count, reviews[review_id]["rationale"])
        for (review_id, source, sponsor, party), count in sorted(
            alignment_counts.items(), key=lambda item: (-item[1], item[0])
        )
    ]
    additions = ""
    if figures:
        additions += (
            "<h2>Figures from the complete saved collection</h2>"
            "<p>These full-snapshot figures do not change with dashboard filters. "
            "Each has an original-size PNG and exact CSV, including ad IDs. "
            "<a href='figures/chart-data.json'>Download all chart data</a> or "
            "<a href='figures/descriptor-evidence.json'>"
            "all descriptor contexts and comparisons</a>."
            "</p>"
            + "".join(
                f"<figure><h3>{escape(chart['title'])}</h3>"
                f"<a href='figures/{escape(chart['png'])}'><img loading='lazy' "
                f"style='width:100%;height:auto' src='figures/{escape(chart['png'])}' "
                f"alt='{escape(chart['description'], quote=True)}'></a>"
                f"<figcaption>{escape(chart['description'])} "
                + " / ".join(
                    f"<a href='figures/{escape(chart[kind])}'>{kind.upper()}</a>"
                    for kind in ("png", "csv")
                )
                + "</figcaption></figure>"
                for chart in figures["charts"]
            )
        )
    if descriptors:
        additions += (
            "<h2>Descriptive language near candidate and party mentions</h2>"
            "<p>This exploratory comparison adapts the question asked in the Harris/Trump "
            "coverage analysis to advertising. It does not import newspaper labels, "
            "sentiment scores or conclusions into this different corpus.</p>"
            f"<p>{escape(descriptors['method'])}</p>"
            "<p>Unlike the issue-family charts, these denominators contain only messages "
            "with eligible explicit mentions. Positive approval lines can be self-description; "
            "a word near a name can describe a policy, another person or a quoted claim. "
            "Neither proximity nor a lexicon entry establishes an advertiser's opinion "
            "of a candidate. The existing context-reviewed examples remain separate.</p>"
            "<p>The general-English lexicon does not cover every political descriptor. "
            "Ideological wording such as radical/liberal is not a complete vocabulary here; "
            "the separate published phrase families measure additional framing language.</p>"
        )
        for target, name in (("D", "Democratic"), ("R", "Republican")):
            group = descriptors["targets"][target]
            additions += f"<h3>Contexts mentioning {name} candidates or the party</h3>"
            additions += table(
                ("Advertiser alignment", "Eligible exact messages"),
                [(party, group["coverage"][party]["total"]) for party in ("D", "R")],
            )
            additions += table(
                ("Lexicon word", "D messages", "R messages", "Log2 odds (D relative to R)"),
                [
                    (
                        row["word"],
                        ratio(row, "D"),
                        ratio(row, "R"),
                        f"{row['log2_odds']:.2f}"
                        if row["log2_odds"] is not None
                        else "Insufficient groups",
                    )
                    for row in group["words"]
                ],
            )
        periods = descriptors["periods"]
        additions += (
            "<h3>Did the opponent-context wording change?</h3>"
            f"<p>Recent: {periods['recent']['start']} through {periods['recent']['end']}. "
            f"Previous: {periods['previous']['start']} through {periods['previous']['end']}. "
            "These are adjacent 90-day first-observed-message windows, not airing histories. "
            "The same exact message enters only its first window. The common-publisher "
            "check retains only publishers represented in both windows; it does not "
            "control candidate, race, format or primary/general composition.</p>"
        )
        for party in ("D", "R"):
            change = descriptors["changes"][party]
            additions += f"<h4>{party}-aligned ads mentioning the opposing party</h4>"
            additions += table(
                ("Cohort", "Recent eligible messages", "Previous eligible messages"),
                [
                    (
                        label,
                        change[key]["coverage"]["recent"]["total"],
                        change[key]["coverage"]["previous"]["total"],
                    )
                    for label, key in (
                        ("All publishers", "all_publishers"),
                        ("Common publishers", "common_publishers"),
                    )
                ],
            )
        additions += (
            "<details><summary>Read the extracted descriptor contexts (unreviewed)</summary>"
            "<p>Windows retain the original source spelling, quotation and negation. "
            "These are extraction results, not manually approved opponent descriptions.</p>"
            + table(
                ("Ad ID", "Advertiser", "Mentioned party", "Lexicon word", "Original context"),
                [
                    (hit["ad_id"], hit["party"], hit["target_party"], hit["word"], hit["context"])
                    for hit in descriptors["evidence"]
                ],
            )
            + "</details>"
        )
    sections = (
        "<h2>Local research snapshot - not published</h2>"
        "<p>All tables describe the saved collection, not national advertising volume. "
        "Evidence downloads retain the complete text, exact match offsets and source hashes. "
        "Figure downloads contain included ad IDs; the local analysis JSON additionally "
        "contains every month, chamber, sponsor-type, publisher, race and phase comparison."
        "</p>" + additions + "<h2>Publisher alignment audit</h2>"
        "<p>The table accounts for reviewed records previously left outside D/R comparisons. "
        "Missing formal FEC party registration does not make electoral alignment unknowable. "
        "D/R describe documented publisher electoral programs, not exclusive endorsements "
        "or formal party membership. Other includes reviewed bipartisan programs; unknown "
        "means the available evidence still does not establish a D/R grouping. All contain "
        "actual ad text. Reviews are bound to each original acquisition hash, and complete "
        "source URLs, filing observations and original classifications are in the downloads. "
        "No text was added by this classification correction.</p>"
        + table(
            ("Sponsor", "Source", "Alignment", "English records", "Review basis"), alignment_rows
        )
        + "<h2>How the observed language differs</h2>"
        "<p>The tables separate issue wording from opponent portrayals. Read the contextual "
        "examples below to determine who is speaking and who is being described. "
        "Primary attacks on same-party candidates and positive self-descriptions are not "
        "evidence of cross-party attacks. No semantic attack rate is estimated.</p>"
        "<p>The saved Democratic-aligned messages include special-interest wording in "
        + ratio(markers["Special interests"], "D")
        + " of messages, compared with "
        + ratio(markers["Special interests"], "R")
        + " on the Republican side. Extreme/radical wording occurs in "
        + ratio(markers["Extreme / radical"], "R")
        + " of Republican-aligned messages and "
        + ratio(markers["Extreme / radical"], "D")
        + " of Democratic-aligned messages. These are whole-text phrase matches, "
        "not counts of independently verified opponent descriptions.</p>"
        "<h3>Vocabulary families, not attack classifications</h3>"
        + table(("Phrase family", "D messages", "R messages"), vocab)
        + "<h2>How much does source composition matter?</h2>"
        "<p>This sensitivity check removes each party's largest publisher by record count ("
        + escape(excluded)
        + "), then recomputes exact-message denominators. The result is not a balanced or "
        "representative sample either; it shows how dependent the apparent contrast is on "
        "the current collection mix. Similar wording across changed-target templates may "
        "still dominate the remaining sample.</p>"
        + table(
            ("Issue wording", "D all", "D excluding largest", "R all", "R excluding largest"),
            sensitivity_rows,
        )
        + "<h2>Historical coverage</h2>"
        "<p>Messages use their earliest saved release, in-scope Google delivery or Snap "
        "scheduled-start month. Snap's dates are planned starts/stops, not verified delivery days. "
        "Pre-2026 Google carryovers are anchored to January, not treated as new launches. "
        "Reported first/last delivery does not prove continuous delivery between those dates. "
        "Publishers count all "
        "records in that month, including repeated messages. Early months are sparse and the "
        "publisher mix changes. A monthly rise is not evidence of more airings or a national "
        "strategy change. Changed-target templates remain distinct.</p>"
        + table(("Month", "D messages", "R messages", "D publishers", "R publishers"), monthly)
        + "<h3>Monthly issue wording</h3>"
        "<p>Each denominator is the party's first-observed exact messages in that month, "
        "not its full-cycle corpus. Multiple families can match the same message.</p>"
        + table(("Month", "Phrase family", "D messages", "R messages"), monthly_issues)
        + "<h2>Publisher composition</h2>"
        "<p>Source-specific messages are deduplicated within each source; summing this column "
        "can therefore exceed the corpus-wide exact-message count.</p>"
        + table(("Publisher", "Alignment", "Records", "Messages"), coverage)
        + "<h2>Comparison boundaries</h2>"
        "<p>Stratum-specific exact messages are deduplicated after filtering. Unknown phases "
        "remain unknown. Primary and general-election records should not be treated as "
        "interchangeable cross-party attacks. Google search/display previews include fundraising "
        "and platform/payer boilerplate: compare formats separately before interpreting "
        "distinctive language as opponent framing. Preview alternatives are not independently "
        "verified delivery records. Native Snap records add local ASR and frame OCR with "
        "explicit machine-extraction uncertainty; speech and overlay lanes do not create "
        "cross-boundary phrase matches.</p>"
        + table(("Dimension", "Stratum", "D messages", "R messages"), subgroup_rows)
        + "<h3>Within-race coverage</h3>"
        "<p>These resolved races contain messages from both alignments. They are not matched "
        "samples: date, publisher, primary/general phase, and extraction mix may still differ. "
        "Read the race-specific issue and vocabulary evidence in the complete JSON.</p>"
        + table(("Race", "D messages", "R messages"), race_rows)
    )
    content = report(dataset).replace(
        "<h2>A closer Senate comparison</h2>", sections + "<h2>A closer Senate comparison</h2>"
    )
    content = content.replace(
        "</head>",
        "<style>figure{margin:2rem 0}table{display:block;max-width:100%;overflow-x:auto}"
        "td{overflow-wrap:anywhere}figcaption{font-size:.85rem;color:#666}"
        "img{max-width:100%}</style></head>",
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
