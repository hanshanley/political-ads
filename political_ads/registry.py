from __future__ import annotations

import csv
import io
import re
import zipfile

from political_ads.http import Client

CANDIDATE_FIELDS = [
    "candidate_id",
    "name",
    "party",
    "election_year",
    "state",
    "office",
    "district",
    "incumbency",
    "status",
    "principal_committee",
    "street1",
    "street2",
    "city",
    "mailing_state",
    "zip",
]
COMMITTEE_FIELDS = [
    "committee_id",
    "name",
    "treasurer",
    "street1",
    "street2",
    "city",
    "state",
    "zip",
    "designation",
    "type",
    "party",
    "filing_frequency",
    "organization_type",
    "connected_organization",
    "candidate_id",
]


def fec_table(client: Client, kind: str) -> list[dict]:
    fields = CANDIDATE_FIELDS if kind == "cn" else COMMITTEE_FIELDS
    data, _ = client.get(
        f"https://www.fec.gov/files/bulk-downloads/2026/{kind}26.zip",
        refresh=True,
    )
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        filename = next(n for n in archive.namelist() if n.endswith(".txt"))
        with archive.open(filename) as file:
            reader = csv.reader(io.TextIOWrapper(file, encoding="utf-8-sig"), delimiter="|")
            return [dict(zip(fields, row, strict=True)) for row in reader]


def candidate_alias(candidate: dict) -> str:
    # Require a full first/last name; a surname alone cannot establish identity.
    parts = candidate["name"].split(",")
    if len(parts) < 2 or not parts[1].split():
        return ""
    last = parts[0].strip()
    first = parts[1].strip().split()[0]
    return f"{first} {last}".casefold()


def candidate_mentions(text: str, candidates: list[dict]) -> list[dict]:
    mentions = []
    for candidate in candidates:
        alias = candidate_alias(candidate)
        if alias and re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text.casefold()):
            mentions.append(
                {
                    key: candidate[key]
                    for key in ("candidate_id", "name", "party", "state", "office", "district")
                }
            )
    return mentions


def enrich(ad: dict, candidates: list[dict]) -> dict:
    result = dict(ad)
    mentions = candidate_mentions(ad["text"] + "\n" + ad["title"], candidates)
    result["candidate_mentions"] = mentions
    if result["race"] == "Unresolved":
        races = {
            (m["state"], m["office"], m["district"]) for m in mentions if m["office"] in {"H", "S"}
        }
        if len(races) == 1:
            state, office, district = races.pop()
            result["state"] = state
            result["chamber"] = "House" if office == "H" else "Senate"
            result["race"] = f"{state}-{int(district):02}" if office == "H" else f"{state}-Senate"
    return result
