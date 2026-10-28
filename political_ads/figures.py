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
from matplotlib.patches import Rectangle
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


def build_figures(dataset: dict, strata: dict, portrayals: dict, output: Path) -> dict:
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

        tone_names = {
            "negative_only": "Negative only",
            "positive_only": "Positive only",
            "mixed": "Both positive and negative",
            "neutral_only": "Neutral only",
        }
        short_frames = {
            "competence": "Ability & judgment",
            "integrity": "Integrity & honesty",
            "interests": "Who they serve",
            "ideology": "Ideology & extremism",
            "connection": "Empathy & connection",
            "leadership": "Strength & leadership",
            "independence": "Independence & loyalty",
            "record": "Actions & policy pledges",
            "safety": "Safety & rights",
            "background": "Background & identity",
            "other": "Other descriptions",
        }

        def portrayal_panels(identity, title, scope, field, labels):
            strategy = field == "ad_strategy"
            groups = (
                portrayals["ad_strategy"]["parties"] if strategy else portrayals["scopes"][scope]
            )
            keys = list(labels)
            if field == "frames":
                keys.sort(
                    key=lambda key: (-max(groups[p][field][key]["share"] or 0 for p in COLORS), key)
                )
            fig, axes = frame(
                title,
                "Share of all unique messages; praise and criticism must occur in the same ad"
                if strategy
                else "Endorsed descriptions of people; each exact message counts once per category",
                height=6.2 if strategy else 5.5 if field == "tones" else 8.0,
                columns=2,
            )
            fig.subplots_adjust(left=0.26, right=0.96, top=0.76, bottom=0.23, wspace=0.22)
            rows = []
            for ax, party in zip(axes, COLORS, strict=True):
                group = groups[party]
                total = (
                    next(iter(group.values()))["total"] if strategy else group["described"]["count"]
                )
                label = (
                    f"{NAMES[party]} ads"
                    if strategy
                    else (
                        "Democrats on Republicans" if party == "D" else "Republicans on Democrats"
                    )
                    if scope == "opponents"
                    else f"{NAMES[party]} ads on their candidates"
                )
                ax.set_title(
                    f"{label}\n{total:,} "
                    + ("unique messages" if strategy else "messages with a description"),
                    loc="left",
                    fontsize=10,
                    color=COLORS[party],
                    pad=17,
                )
                for index, key in enumerate(keys):
                    value = group[key] if strategy else group[field][key]
                    rows.append(
                        {"scope": scope, "label": labels[key], "key": key, "party": party, **value}
                    )
                    if value["share"] is not None:
                        share = value["share"]
                        ax.barh(index, share, height=0.5, color=COLORS[party], zorder=3)
                        inside = share >= 0.54
                        ax.text(
                            share - 0.025 if inside else share + 0.025,
                            index,
                            f"{share:.1%}  ({value['count']:,}/{value['total']:,})",
                            va="center",
                            ha="right" if inside else "left",
                            fontsize=8.5,
                            color="white" if inside else COLORS[party],
                            zorder=4,
                        )
                ax.set_yticks(
                    range(len(keys)),
                    [labels[key] for key in keys] if party == "D" else [""] * len(keys),
                )
                ax.invert_yaxis()
                ax.set_ylim(len(keys) - 0.55, -0.55)
                ax.set_xlim(0, 1.02)
                ax.set_xticks(
                    [0, 0.25, 0.5, 0.75, 1], ["0%", "25%", "50%", "75%", "100%"], fontsize=8
                )
                ax.grid(axis="x", zorder=0)
                ax.set_axisbelow(True)
                if not total:
                    ax.text(
                        0.5,
                        0.5,
                        "No messages" if strategy else "No reviewed descriptions",
                        transform=ax.transAxes,
                        ha="center",
                        color="#777777",
                    )
            save(
                fig,
                identity,
                title,
                "Own-side praise, opponent criticism or both within the same ad; "
                "shares of all unique messages."
                if strategy
                else "Context-coded message shares among reviewed ads with "
                "an eligible person description.",
                rows,
                (
                    "People and party collectives included. 'Only' refers to these two signals; "
                    "neither is not neutral. Missing/uncertain reviews remain separate. "
                    if strategy
                    else (
                        "Exclusive tone categories; no description is not neutral. "
                        if field == "tones"
                        else "Frames overlap; multiple claims count once per frame. "
                    )
                )
                + "Quoted opponents and rebutted claims excluded. AI-assisted, not human gold.",
            )

        portrayal_panels(
            "ad-strategy",
            "Do ads praise, attack, or combine both?",
            "all",
            "ad_strategy",
            {
                key: textwrap.fill(label, 25)
                for key, label in portrayals["ad_strategy"]["categories"].items()
            },
        )
        for scope, prefix, name in (
            ("opponents", "opponent", "their opponents"),
            ("self", "self", "their own candidates"),
        ):
            portrayal_panels(
                f"{prefix}-tone", f"How they describe {name}", scope, "tones", tone_names
            )
            portrayal_panels(
                f"{prefix}-frames",
                f"What they say about {name}",
                scope,
                "frames",
                {
                    key: short_frames.get(key, label)
                    for key, label in dataset["portrayal_codebook"]["frames"].items()
                },
            )

        title = "What has actually been reviewed?"
        fig, (ax,) = frame(
            title, "Review status of the complete exact-message collection", height=5.2
        )
        fig.subplots_adjust(left=0.15, right=0.95, top=0.73, bottom=0.25)
        status_colors = {
            "reviewed": "#49685B",
            "uncertain": "#B49A67",
            "unreviewed": "#D6D3CC",
            "stale": "#A97B68",
        }
        rows = []
        for index, party in enumerate(COLORS):
            left = 0
            for status, color in status_colors.items():
                value = portrayals["coverage"][party][status]
                rows.append({"label": status, "party": party, **value})
                share = value["share"] or 0
                if share:
                    ax.barh(index, share, left=left, color=color, height=0.42)
                    if share >= 0.12:
                        ax.text(
                            left + share / 2,
                            index,
                            f"{value['count']:,}  ({share:.1%})",
                            ha="center",
                            va="center",
                            color="white" if status == "reviewed" else "#333333",
                            fontsize=10,
                        )
                left += share
            ax.text(
                1.02,
                index,
                f"{portrayals['coverage'][party]['reviewed']['total']:,} messages",
                va="center",
                fontsize=9,
            )
            ax.text(
                0,
                index + 0.32,
                "; ".join(
                    f"{status.capitalize()} {portrayals['coverage'][party][status]['count']:,}"
                    for status in status_colors
                ),
                fontsize=8,
                color="#555555",
                va="center",
            )
        ax.set_yticks([0, 1], ["Democratic", "Republican"])
        ax.invert_yaxis()
        ax.set_ylim(1.5, -0.45)
        ax.set_xlim(0, 1.2)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1], ["0%", "25%", "50%", "75%", "100%"])
        ax.grid(axis="x")
        ax.set_axisbelow(True)
        for i, (status, color) in enumerate(status_colors.items()):
            x = 0.15 + i * 0.2
            fig.add_artist(
                Rectangle((x, 0.816), 0.012, 0.022, color=color, transform=fig.transFigure)
            )
            fig.text(x + 0.02, 0.82, status.capitalize(), color="#555555", fontsize=10)
        save(
            fig,
            "portrayal-coverage",
            title,
            "Reviewed, uncertain, unreviewed and stale exact messages by advertiser alignment.",
            rows,
            "Coverage measures completion, not classification accuracy. "
            "Missing reviews never become neutral labels.",
        )

    order = (
        "ad-strategy",
        "opponent-tone",
        "self-tone",
        "opponent-frames",
        "self-frames",
        "portrayal-coverage",
        "issue-language",
        "source-sensitivity",
        "publisher-composition",
        "monthly-coverage",
        "monthly-issues",
    )
    charts.sort(key=lambda chart: order.index(chart["id"]))
    manifest = {
        "version": "figures-3",
        "snapshot_id": dataset["snapshot_id"],
        "until": dataset["until"],
        "publication_status": "local_only",
        "charts": charts,
    }
    write_json(output / "manifest.json", manifest)
    write_json(output / "chart-data.json", manifest | {"data": all_data})
    write_json(output / "portrayal-evidence.json", portrayals)
    remove_retired_figures(output)
    return manifest


def remove_retired_figures(output: Path) -> None:
    retired = (
        "portrayal-language",
        "descriptors-D",
        "descriptors-R",
        "descriptor-change-D",
        "descriptor-change-R",
    )
    for identity in retired:
        for kind in ("png", "csv"):
            (output / f"{identity}.{kind}").unlink(missing_ok=True)
    (output / "descriptor-evidence.json").unlink(missing_ok=True)


def month_name(month: str) -> str:
    return ("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())[int(month[5:7]) - 1]
