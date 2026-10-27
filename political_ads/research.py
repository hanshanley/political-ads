from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path

from political_ads.analysis import stratified_comparisons
from political_ads.cli import write_json
from political_ads.publication import csv_export, prepare, report, validate_dataset


def research(root: Path) -> dict:
    dataset = prepare(root)
    validate_dataset(dataset)
    strata = stratified_comparisons(dataset["ads"], dataset["codebook"])
    result = {
        "analysis_version": "stratified-1",
        "publication_status": "local_only",
        "monthly_basis": "First release, in-scope Google delivery or Snap scheduled start "
        "of each exact party/message; pre-2026 carryovers anchored to January, not new launches",
        "stratum_basis": "Exact party/messages deduplicated after each non-temporal filter",
        "dataset": dataset,
        "comparisons": strata,
    }
    output = root / "outputs"
    write_json(output / "analysis.json", result)
    (output / "analysis-ads.csv").write_text(csv_export(dataset["ads"]), newline="")
    (output / "analysis.html").write_text(research_report(dataset, strata))
    return result


def research_report(dataset: dict, strata: dict) -> str:
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
    sections = (
        "<h2>Local research snapshot - not published</h2>"
        "<p>All tables describe the saved collection, not national advertising volume. "
        "The complete JSON contains text, exact match offsets, source hashes, and included ad IDs "
        "for every comparison, including month, chamber, sponsor type, publisher, race, and phase."
        "</p><h2>Publisher alignment audit</h2>"
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
    return (
        content.replace("data/ads.csv", "analysis-ads.csv")
        .replace("data/dataset.json", "analysis.json")
        .replace(
            "<a href='./'>The Margin of Error / Political ads</a>",
            "<p><strong>LOCAL ONLY - website publication is on hold.</strong></p>",
        )
        .replace(
            "<link rel='canonical' href='https://www.themarginoferror.com/political-ads/report.html'>",
            "",
        )
    )
