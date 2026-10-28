from __future__ import annotations

import csv
import io
import json
import math
import textwrap
from collections import Counter
from hashlib import sha256
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, PercentFormatter

from political_ads.analysis import publisher, unique_messages
from political_ads.cli import write_json
from political_ads.publication import spreadsheet_cell
from political_ads.schema import observation_date

COLORS = {"D": "#3D6F8C", "R": "#C85A3D"}
NAMES = {"D": "Democratic", "R": "Republican"}
STYLE = {
    "figure.facecolor": "#F7F5F0",
    "axes.facecolor": "#F7F5F0",
    "savefig.facecolor": "#F7F5F0",
    "font.family": "DejaVu Serif",
    "font.size": 10,
    "text.color": "#1A1A1A",
    "axes.labelcolor": "#555555",
    "xtick.color": "#666666",
    "ytick.color": "#444444",
    "axes.edgecolor": "#D6D3CC",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
    "grid.color": "#D6D3CC",
    "grid.alpha": 0.6,
    "grid.linewidth": 0.5,
    "xtick.major.size": 0,
    "ytick.major.size": 0,
    "text.parse_math": False,
}


def months_through(until: str) -> list[str]:
    return [f"2026-{month:02}" for month in range(1, int(until[5:7]) + 1)]


def choose_words(group: dict) -> list[dict]:
    if not group["rankable"]:
        return []
    rows = group["words"]
    positive = sorted(
        [row for row in rows if row["log2_odds"] > 0],
        key=lambda row: (-row["log2_odds"], row["word"]),
    )[:5]
    negative = sorted(
        [row for row in rows if row["log2_odds"] < 0],
        key=lambda row: (row["log2_odds"], row["word"]),
    )[:5]
    return sorted(positive + negative, key=lambda row: (row["log2_odds"], row["word"]))


def build_figures(dataset: dict, strata: dict, descriptors: dict, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    charts = []
    all_data = {}

    def frame(title, subtitle, *, height=5.7, columns=1):
        fig, axes = plt.subplots(1, columns, figsize=(10.5, height), squeeze=False)
        fig.subplots_adjust(left=0.28, right=0.93, top=0.79, bottom=0.23, wspace=0.7)
        fig.text(0.06, 0.95, title, fontsize=18, weight="bold", va="top")
        fig.text(0.06, 0.885, subtitle, fontsize=9.5, color="#666666", va="top")
        return fig, axes[0]

    def save(fig, identity, title, description, rows, note):
        footer = (
            f"Source: saved political-ads corpus through {dataset['until']}. "
            + note
            + f"\nSnapshot {dataset['snapshot_id'][:12]}. Research only; not national ad volume."
        )
        fig.text(
            0.06,
            0.065,
            "\n".join(textwrap.wrap(footer.split("\n")[0], 135)) + "\n" + footer.split("\n")[1],
            fontsize=7.6,
            color="#666666",
            style="italic",
            va="bottom",
        )
        fig.savefig(output / f"{identity}.png", dpi=200, metadata={"Software": "political-ads"})
        plt.close(fig)
        keys = list(dict.fromkeys(key for row in rows for key in row)) or ["label"]
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=["snapshot_id", "until", *keys])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {"snapshot_id": dataset["snapshot_id"], "until": dataset["until"]}
                | {
                    key: spreadsheet_cell(
                        json.dumps(value) if isinstance(value, (list, dict)) else value
                    )
                    for key, value in row.items()
                }
            )
        (output / f"{identity}.csv").write_text(stream.getvalue(), newline="")
        charts.append(
            {
                "id": identity,
                "title": title,
                "description": description,
                "png": f"{identity}.png",
                "csv": f"{identity}.csv",
                "sha256": {
                    kind: sha256((output / f"{identity}.{kind}").read_bytes()).hexdigest()
                    for kind in ("png", "csv")
                },
            }
        )
        all_data[identity] = {"description": description, "note": note, "rows": rows}

    def legend(fig):
        fig.text(0.64, 0.885, "Democratic", color=COLORS["D"], fontsize=9.5)
        fig.text(0.79, 0.885, "Republican", color=COLORS["R"], fontsize=9.5)

    with plt.rc_context(STYLE):
        months = months_through(dataset["until"])
        messages = unique_messages(dataset["ads"])
        monthly = [
            {
                "month": month,
                "party": party,
                "count": len(
                    ids := [
                        ad["id"]
                        for ad in messages
                        if ad["alignment"] == party and observation_date(ad)[:7] == month
                    ]
                ),
                "ad_ids": ids,
            }
            for month in months
            for party in COLORS
        ]
        title = "Messages in the saved collection"
        fig, (ax,) = frame(title, "First observed month, not spending or airings")
        fig.subplots_adjust(left=0.10)
        legend(fig)
        for party, shift in (("D", -0.18), ("R", 0.18)):
            values = [row["count"] for row in monthly if row["party"] == party]
            bars = ax.bar(
                [i + shift for i in range(len(months))], values, width=0.32, color=COLORS[party]
            )
            ax.bar_label(bars, padding=3, fontsize=7.5)
        ax.set_xticks(range(len(months)), [month_name(month) for month in months])
        ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))
        ax.set_ylabel("Exact unique messages")
        ax.grid(axis="y")
        ax.set_axisbelow(True)
        ax.margins(y=0.18)
        save(
            fig,
            "monthly-coverage",
            title,
            "Monthly D/R first-observed exact-message counts.",
            monthly,
            "Carryovers start in January; Snap dates are scheduled. The final month is partial.",
        )

        for identity, key, title in (
            ("issue-language", "issues", "What issues appear in the wording?"),
            ("portrayal-language", "portrayals", "The vocabulary of contrast"),
        ):
            rows = strata["overall"][key]
            fig, (ax,) = frame(title, "Phrase-family matches per exact unique message", height=6.7)
            fig.subplots_adjust(right=0.78)
            legend(fig)
            export = []
            for index, row in enumerate(rows):
                for party, shift in (("D", -0.17), ("R", 0.17)):
                    value = row[party]
                    if value["share"] is not None:
                        ax.barh(index + shift, value["share"], height=0.28, color=COLORS[party])
                    ax.text(
                        1.025,
                        index + shift,
                        f"{party} {value['count']}/{value['total']}"
                        if value["total"]
                        else f"{party} no messages",
                        fontsize=8,
                        color=COLORS[party],
                        va="center",
                        transform=ax.get_yaxis_transform(),
                    )
                    export.append({"label": row["label"], "party": party, **value})
            ax.set_yticks(range(len(rows)), [textwrap.fill(row["label"], 25) for row in rows])
            ax.invert_yaxis()
            maximum = max((row[p]["share"] or 0 for row in rows for p in COLORS), default=0)
            ax.set_xlim(0, max(0.1, math.ceil(maximum * 10) / 10))
            ax.xaxis.set_major_locator(MaxNLocator(nbins=6, steps=[1, 2, 5, 10]))
            ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
            ax.grid(axis="x")
            ax.set_axisbelow(True)
            save(
                fig,
                identity,
                title,
                "Exact phrase-family presence; counts and denominators shown.",
                export,
                "Categories overlap. Quotes, denials and self-promotion are included; "
                "not attack rates.",
            )

        title = "Issue wording over the cycle"
        labels = sorted(dataset["codebook"]["issues"])
        panel_rows = max(1, math.ceil(len(labels) / 2))
        fig, axes = plt.subplots(
            panel_rows, 2, figsize=(10.5, max(7.5, 2.4 * panel_rows)), squeeze=False
        )
        fig.subplots_adjust(left=0.10, right=0.95, top=0.88, bottom=0.12, hspace=0.65, wspace=0.28)
        fig.text(0.06, 0.965, title, fontsize=18, weight="bold")
        fig.text(
            0.06,
            0.935,
            "Share of each month's first-observed exact messages",
            fontsize=10,
            color="#666666",
        )
        fig.text(0.64, 0.935, "Democratic", color=COLORS["D"])
        fig.text(0.79, 0.935, "Republican", color=COLORS["R"])
        export = []
        for ax, label in zip(axes.flat, labels, strict=False):
            ax.set_title(label, fontsize=10, loc="left")
            for party in COLORS:
                values = []
                for month in months:
                    row = next(
                        (
                            row
                            for row in strata["month"].get(month, {}).get("issues", [])
                            if row["label"] == label
                        ),
                        None,
                    )
                    value = (
                        row[party] if row else {"count": 0, "total": 0, "share": None, "ad_ids": []}
                    )
                    values.append(math.nan if value["share"] is None else value["share"])
                    export.append({"month": month, "label": label, "party": party, **value})
                ax.plot(
                    range(len(months)),
                    values,
                    color=COLORS[party],
                    linewidth=1.5,
                    marker="o",
                    markersize=3,
                )
            ticks = sorted({*range(0, len(months), 2), len(months) - 1})
            ax.set_xticks(ticks, [month_name(months[i]) for i in ticks], fontsize=8)
            ax.set_ylim(0, 1)
            ax.set_yticks([0, 0.5, 1], ["0%", "50%", "100%"], fontsize=8)
            ax.grid(axis="y")
        for ax in list(axes.flat)[len(labels) :]:
            ax.remove()
        save(
            fig,
            "monthly-issues",
            title,
            "All issue families by first-observed month; missing denominators break lines.",
            export,
            "No line is drawn for a party with no messages. "
            "Changing sources and partial months limit comparisons.",
        )

        title = "Who supplies the observed ads?"
        fig, axes = frame(
            title,
            "Share of each party's source records, not reach or spending",
            height=6.7,
            columns=2,
        )
        fig.subplots_adjust(left=0.22, right=0.94, wspace=1.55)
        export = []
        for ax, party in zip(axes, COLORS, strict=True):
            scope = [ad for ad in dataset["ads"] if ad["alignment"] == party]
            counts = Counter(publisher(ad) for ad in scope)
            top = sorted(counts, key=lambda name: (-counts[name], name))[:5]
            groups = [(name, [ad["id"] for ad in scope if publisher(ad) == name]) for name in top]
            remaining = [ad["id"] for ad in scope if publisher(ad) not in top]
            if remaining:
                groups.append(("All other publishers", remaining))
            ax.set_title(
                f"{NAMES[party]}: {len(scope):,} records",
                fontsize=10,
                loc="left",
                color=COLORS[party],
            )
            for index, (name, ids) in enumerate(groups):
                share = len(ids) / len(scope) if scope else None
                ax.barh(index, share or 0, color=COLORS[party], height=0.55)
                ax.text((share or 0) + 0.025, index, f"{len(ids):,}", fontsize=8, va="center")
                export.append(
                    {
                        "publisher": name,
                        "party": party,
                        "count": len(ids),
                        "total": len(scope),
                        "share": share,
                        "ad_ids": ids,
                    }
                )
            ax.set_yticks(
                range(len(groups)), [textwrap.fill(name, 23) for name, _ in groups], fontsize=8
            )
            ax.invert_yaxis()
            ax.set_xlim(0, 1.18)
            ax.set_xticks([0, 0.5, 1], ["0%", "50%", "100%"])
            ax.grid(axis="x")
            ax.set_axisbelow(True)
        save(
            fig,
            "publisher-composition",
            title,
            "Largest five publishers per party and all remaining publishers.",
            export,
            "Named sponsors/publishers are grouped across acquisition-source IDs; "
            "this is not a sole-payer claim. "
            "Mirrored messages can occur across publishers.",
        )

        title = "How dependent are the issue gaps on sources?"
        fig, axes = frame(
            title,
            "Filled: all messages     Hollow: excluding the party's largest publisher",
            height=6.7,
            columns=2,
        )
        fig.subplots_adjust(left=0.28, right=0.95, wspace=0.25)
        reduced = strata["sensitivity"]["without_largest_publisher_per_party"]["issues"]
        maximum = max(
            (row[p]["share"] or 0 for row in strata["overall"]["issues"] + reduced for p in COLORS),
            default=0,
        )
        upper = max(0.1, math.ceil(maximum * 10) / 10)
        export = []
        for ax, party in zip(axes, COLORS, strict=True):
            ax.set_title(NAMES[party], color=COLORS[party], loc="left", fontsize=11)
            for index, (full, less) in enumerate(
                zip(strata["overall"]["issues"], reduced, strict=True)
            ):
                a, b = full[party]["share"], less[party]["share"]
                if a is not None and b is not None:
                    ax.plot([a, b], [index, index], color="#AAAAAA", linewidth=1)
                if a is not None:
                    ax.scatter(a, index, color=COLORS[party], s=30, zorder=3)
                if b is not None:
                    ax.scatter(
                        b, index, edgecolor=COLORS[party], facecolor="#F7F5F0", s=38, zorder=4
                    )
                for group, row in (("all", full), ("without_largest", less)):
                    export.append(
                        {"label": full["label"], "party": party, "group": group, **row[party]}
                    )
            ax.set_yticks(
                range(len(reduced)),
                [textwrap.fill(row["label"], 25) for row in reduced]
                if party == "D"
                else [""] * len(reduced),
            )
            ax.invert_yaxis()
            ax.set_xlim(-upper * 0.025, upper * 1.025)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=6, steps=[1, 2, 5, 10]))
            ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
            ax.grid(axis="x")
        exclusions = "; ".join(
            f"{p}: {name}" for p, name in strata["sensitivity"]["excluded_publishers"].items()
        )
        save(
            fig,
            "source-sensitivity",
            title,
            "Issue shares before and after removing the largest record publisher.",
            export,
            f"Excluded {exclusions}. Missing denominators have no point. "
            "Neither sample is representative.",
        )

        def word_chart(identity, title, group, first, second, *, common=None, note=""):
            rows = choose_words(group)
            totals = group["coverage"]
            names = {"D": "D advertisers", "R": "R advertisers"}
            subtitle = (
                f"{names.get(first, first)}: {totals[first]['total']} messages; "
                f"{names.get(second, second)}: {totals[second]['total']} messages"
            )
            fig, (ax,) = frame(title, subtitle, height=6.2)
            fig.subplots_adjust(left=0.18, right=0.72)
            common_by_word = (
                {row["word"]: row for row in common["words"]}
                if common and common["rankable"]
                else {}
            )
            for index, row in enumerate(rows):
                score = row["log2_odds"]
                color = (
                    COLORS.get(first, COLORS.get(identity[-1], COLORS["D"]))
                    if score > 0
                    else (COLORS.get(second, "#85817A"))
                )
                ax.barh(index, score, height=0.5, color=color)
                if other := common_by_word.get(row["word"]):
                    ax.scatter(
                        other["log2_odds"],
                        index,
                        facecolor="#F7F5F0",
                        edgecolor="#333333",
                        s=28,
                        zorder=4,
                    )
                ax.text(
                    1.025,
                    index,
                    f"{first} {row[first]['count']}/{row[first]['total']}  "
                    f"{second} {row[second]['count']}/{row[second]['total']}",
                    transform=ax.get_yaxis_transform(),
                    va="center",
                    fontsize=8,
                )
            ax.set_yticks(range(len(rows)), [row["word"] for row in rows])
            ax.invert_yaxis()
            ax.axvline(0, color="#888888", linewidth=0.8)
            extent = (
                max(
                    [abs(row["log2_odds"]) for row in rows]
                    + [
                        abs(common_by_word[row["word"]]["log2_odds"])
                        for row in rows
                        if row["word"] in common_by_word
                    ]
                    + [1]
                )
                * 1.12
            )
            ax.set_xlim(-extent, extent)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
            ax.set_xlabel(
                f"More {names.get(second, second)}  \u2190  log\u2082 message odds ratio  "
                f"\u2192  More {names.get(first, first)}",
                fontsize=9,
            )
            ax.grid(axis="x")
            ax.set_axisbelow(True)
            if not rows:
                ax.text(
                    0.5,
                    0.5,
                    "No ranked contrast at the support thresholds\n"
                    "(minimum 10 messages per group; 3 word matches)",
                    transform=ax.transAxes,
                    ha="center",
                    va="center",
                    color="#666666",
                    fontsize=10,
                )
            export = [
                {
                    "word": row["word"],
                    "group": name,
                    "cohort": cohort,
                    "displayed": row["word"] in {item["word"] for item in rows}
                    and row["log2_odds"] is not None,
                    "log2_odds": row["log2_odds"],
                    **row[name],
                }
                for cohort, comparison in (("all", group), ("common_publishers", common))
                if comparison
                for row in comparison["words"]
                for name in (first, second)
            ]
            save(
                fig,
                identity,
                title,
                "Supported lexicon-word contrasts in unreviewed mention contexts.",
                export,
                "At most five supported words per direction. "
                "A nearby adjective is not a verified target description. " + note,
            )

        for target in COLORS:
            word_chart(
                f"descriptors-{target}",
                f"Words near {NAMES[target]} mentions",
                descriptors["targets"][target],
                "D",
                "R",
                note="Negation, quotation, policy language and self-description are retained.",
            )
        periods = descriptors["periods"]
        for party in COLORS:
            change = descriptors["changes"][party]
            period_note = (
                f"Recent {periods['recent']['start']} to {periods['recent']['end']}; "
                f"previous {periods['previous']['start']} to {periods['previous']['end']}. "
                "Hollow: publishers present in both periods, if supported. "
                "Not significance intervals."
            )
            word_chart(
                f"descriptor-change-{party}",
                f"{NAMES[party]} wording near opposing-party mentions",
                change["all_publishers"],
                "recent",
                "previous",
                common=change["common_publishers"],
                note=period_note,
            )

    manifest = {
        "version": "figures-2",
        "snapshot_id": dataset["snapshot_id"],
        "until": dataset["until"],
        "publication_status": "local_only",
        "charts": charts,
    }
    write_json(output / "manifest.json", manifest)
    write_json(output / "chart-data.json", manifest | {"data": all_data})
    write_json(output / "descriptor-evidence.json", descriptors)
    return manifest


def month_name(month: str) -> str:
    return ("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())[int(month[5:7]) - 1]
