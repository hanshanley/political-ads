from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter, defaultdict, deque
from datetime import date, datetime
from pathlib import Path
from time import sleep
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from zipfile import ZipFile

from bs4 import BeautifulSoup

from political_ads.cli import read_json, write_json
from political_ads.http import USER_AGENT, Client
from political_ads.images import recognize_image
from political_ads.registry import candidate_alias
from political_ads.schema import END, START, Ad, digest, in_window
from political_ads.sources import SOURCES, language_of

BUNDLE = "google-political-ads-transparency-bundle.zip"
CREATIVE_ENDPOINT = "https://adstransparency.google.com/anji/_/rpc/LookupService/GetCreativeById"
FEDERAL_PUBLISHERS = {
    "C00027466": ("nrsc", "NRSC", "R", "party", "Senate"),
    "C00075820": ("nrcc", "NRCC", "R", "party", "House"),
    "C00000935": ("dccc", "DCCC", "D", "party", "House"),
    "C00042366": ("dscc", "DSCC", "D", "party", "Senate"),
    "C00571703": ("slf", "Senate Leadership Fund", "R", "outside_group", "Senate"),
    "C00504530": ("clf", "Congressional Leadership Fund", "R", "outside_group", "House"),
    "C00495028": ("hmp", "House Majority PAC", "D", "outside_group", "House"),
    "C00484642": ("smp", "Senate Majority PAC", "D", "outside_group", "Senate"),
    "C00865444": ("winsenate", "WinSenate", "D", "outside_group", "Senate"),
}


def federal_advertisers(advertisers: list[dict], candidates: list[dict]) -> dict:
    committees = defaultdict(dict)
    for candidate in candidates:
        if (
            candidate["office"] in {"H", "S"}
            and candidate["election_year"] == "2026"
            and candidate["party"] in {"DEM", "REP"}
            and candidate["principal_committee"]
        ):
            committees[candidate["principal_committee"]][candidate["candidate_id"]] = candidate
    result = {}
    for advertiser in advertisers:
        identifiers = set(re.findall(r"\bC\d{8}\b", advertiser["Public_IDs_List"]))
        if len(identifiers) != 1:
            continue
        matches = []
        for committee in identifiers:
            if committee in FEDERAL_PUBLISHERS:
                source, sponsor, alignment, kind, chamber = FEDERAL_PUBLISHERS[committee]
                matches.append(
                    dict(
                        source=source,
                        sponsor=sponsor,
                        alignment=alignment,
                        sponsor_type=kind,
                        chamber=chamber,
                        race="Unresolved",
                        state="",
                        committee_id=committee,
                        candidate_id="",
                    )
                )
            elif len(committees[committee]) == 1:
                candidate = next(iter(committees[committee].values()))
                source = next(
                    (
                        s.id
                        for s in SOURCES
                        if s.sponsor_type == "candidate"
                        and candidate_alias(candidate)
                        and candidate_alias(candidate) in s.sponsor.casefold()
                    ),
                    "fec-" + committee,
                )
                matches.append(
                    dict(
                        source=source,
                        sponsor=advertiser["Advertiser_Name"],
                        alignment="D" if candidate["party"] == "DEM" else "R",
                        sponsor_type="candidate",
                        chamber="House" if candidate["office"] == "H" else "Senate",
                        race=(
                            f"{candidate['state']}-{int(candidate['district']):02}"
                            if candidate["office"] == "H"
                            else f"{candidate['state']}-Senate"
                        ),
                        state=candidate["state"],
                        committee_id=committee,
                        candidate_id=candidate["candidate_id"],
                    )
                )
        if len(matches) == 1:
            result[advertiser["Advertiser_ID"]] = matches[0]
    return result


def discover_google(root: Path, until: str) -> dict:
    csv.field_size_limit(16_000_000)
    candidates = read_json(root / "data/site/candidates.json", {})["candidates"]
    with ZipFile(root / "data/raw" / BUNDLE) as archive:
        updated = archive.read("google-political-ads-updated.csv").decode().splitlines()[-1]
        with archive.open("google-political-ads-advertiser-stats.csv") as handle:
            advertisers = federal_advertisers(
                list(csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8-sig"))), candidates
            )
        leads = []
        total = us = 0
        with archive.open("google-political-ads-creative-stats.csv") as handle:
            for row in csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8-sig")):
                total += 1
                if not re.search(r"\bUS\b", row["Regions"]) or not in_window(
                    row["Date_Range_Start"], row["Date_Range_End"], until
                ):
                    continue
                us += 1
                sponsor = advertisers.get(row["Advertiser_ID"])
                if sponsor:
                    leads.append(
                        {
                            key: row[key]
                            for key in (
                                "Ad_ID",
                                "Ad_URL",
                                "Ad_Type",
                                "Advertiser_ID",
                                "Advertiser_Name",
                                "Regions",
                                "Date_Range_Start",
                                "Date_Range_End",
                                "First_Served_Timestamp",
                                "Last_Served_Timestamp",
                            )
                        }
                        | {"publisher": sponsor}
                    )
    result = dict(
        updated=updated,
        until=until,
        rows_scanned=total,
        us_in_window=us,
        leads=leads,
        scope="Exact public FEC IDs: unambiguous 2026 D/R principal committees and "
        "explicitly registered federal party/outside-group publishers; not every advertiser.",
    )
    write_json(root / "data/raw/google-discovery.json", result)
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "leads"}
            | {
                "federal_leads": len(leads),
                "by_party": dict(Counter(r["publisher"]["alignment"] for r in leads)),
                "by_type": dict(Counter(r["Ad_Type"] for r in leads)),
            }
        ),
        flush=True,
    )
    return result


def creative_payload(root: Path, lead: dict, offline: bool) -> dict:
    path = root / "data/raw/google-creatives" / (lead["Ad_ID"] + ".json")
    if path.exists():
        return read_json(path, {})
    if offline:
        raise FileNotFoundError(f"No cached Google creative: {lead['Ad_ID']}")
    params = {
        "1": lead["Advertiser_ID"],
        "2": lead["Ad_ID"],
        "5": {"1": 2, "2": 0, "3": 2840},
    }
    request = Request(
        CREATIVE_ENDPOINT,
        data=urlencode({"f.req": json.dumps(params, separators=(",", ":"))}).encode(),
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urlopen(request, timeout=45) as response:
        payload = json.load(response)
    record = payload.get("1", {})
    if record.get("1") != lead["Advertiser_ID"] or record.get("2") != lead["Ad_ID"]:
        raise ValueError("Google creative identity does not match the requested record")
    write_json(path, payload)
    sleep(0.5)
    return payload


def preview_images(payload: dict) -> list[str]:
    result = []
    for preview in payload.get("1", {}).get("5", []):
        html = preview.get("3", {}).get("2", "")
        soup = BeautifulSoup(html, "html.parser")
        # A video poster is not an image ad. Only accept the viewer's direct image previews.
        if soup.find(["iframe", "video"]) or soup.get_text(strip=True):
            continue
        for image in soup.find_all("img"):
            url = image.get("src", "")
            parsed = urlsplit(url)
            if (
                parsed.scheme == "https"
                and parsed.hostname == "tpc.googlesyndication.com"
                and parsed.path.startswith("/archive/simgad/")
                and url not in result
            ):
                result.append(url)
    return result


def us_delivery(lead: dict, payload: dict) -> tuple[str, str]:
    for region in payload.get("1", {}).get("17", []):
        if region.get("1") == 2840 and region.get("4") and region.get("5"):
            return tuple(
                datetime.strptime(str(region[key]), "%Y%m%d").date().isoformat()
                for key in ("4", "5")
            )
    if lead["Regions"] == "US":
        return lead["Date_Range_Start"], lead["Date_Range_End"]
    raise ValueError("No verifiable U.S.-specific delivery interval for a multi-region creative")


def preview_ad(lead: dict, payload: dict, url: str, image_hash: str, ocr: dict) -> dict:
    if ocr.get("image_frame_count", 1) != 1:
        raise ValueError("Animated images require complete frame extraction")
    start, end = us_delivery(lead, payload)
    publisher = lead["publisher"]
    segments = [
        {
            "text": line["text"],
            "kind": "image_ocr",
            "voice": "unreviewed",
            "start_seconds": None,
            "end_seconds": None,
            "confidence": line["confidence"],
            "image_bounds": line["bounds"],
            "image_hash": image_hash,
            "image_url": url,
            "coordinate_system": ocr["coordinate_system"],
            "extraction_engine": ocr["engine"],
            "google_ad_id": lead["Ad_ID"],
            "google_advertiser_id": lead["Advertiser_ID"],
            "fec_committee_id": publisher["committee_id"],
            "reported_ad_type": lead["Ad_Type"],
        }
        for line in ocr["lines"]
        if line["text"].strip()
    ]
    text = "\n".join(s["text"] for s in segments)
    if not segments or re.fullmatch(r"paid for by[^\n]*", text, re.I):
        raise ValueError("No substantive creative text")
    return Ad(
        id="google-" + lead["Ad_ID"] + "-" + digest(url)[:12],
        source=publisher["source"] + "-google",
        source_url=lead["Ad_URL"],
        source_record_id=lead["Ad_ID"],
        title=f"Google {lead['Ad_Type'].lower()} ad {lead['Ad_ID']}",
        sponsor=publisher["sponsor"],
        sponsor_type=publisher["sponsor_type"],
        alignment=publisher["alignment"],
        published=start,
        observed=date.today().isoformat(),
        text=text,
        segments=segments,
        source_hash=digest(json.dumps([lead, payload, image_hash, ocr], sort_keys=True)),
        date_basis="delivery",
        delivery_start=start,
        delivery_end=end,
        placement="google_reported_delivery",
        race=publisher["race"],
        state=publisher["state"],
        chamber=publisher["chamber"],
        language=language_of(text),
        language_basis="Local English OCR plus seeded language detection; uncertain text excluded",
        media_urls=[url],
        quality_flags=[
            "image_ocr_may_misrecognize_words",
            "image_reading_order_unverified",
            "google_preview_variant_not_invented_dynamic_combination",
            "preview_delivery_not_individually_verified",
            "google_preview_may_truncate_dynamic_text",
            "google_format_includes_fundraising_and_search_ads",
        ],
        attribution_basis=(
            f"Google public advertiser FEC ID {publisher['committee_id']} joined to "
            "2026 federal principal committee "
            f"{publisher['candidate_id'] or 'or reviewed publisher'}. "
            "Candidate race is the sponsor's seat, not an inferred target. Each native "
            "image preview is kept separately; no dynamic alternatives concatenated. "
            "Delivery interval is Google-reported U.S. delivery for the parent creative, not "
            "proof each preview variant was individually served or a publication date."
        ),
    ).to_dict()


def coverage_order(leads: list[dict]) -> list[dict]:
    groups = defaultdict(lambda: defaultdict(list))
    for lead in sorted(leads, key=lambda r: (r["Date_Range_Start"], r["Ad_ID"])):
        if lead["Ad_Type"] in {"IMAGE", "TEXT"}:
            groups[lead["publisher"]["source"]][lead["Date_Range_Start"][:7]].append(lead)
    publishers = []
    for source in sorted(groups):
        months = [deque(rows) for _, rows in sorted(groups[source].items())]
        ordered = []
        while months:
            ordered.extend(month.popleft() for month in months)
            months = [month for month in months if month]
        publishers.append(deque(ordered))
    ordered = []
    while publishers:
        ordered.extend(publisher.popleft() for publisher in publishers)
        publishers = [publisher for publisher in publishers if publisher]
    return ordered


def collect_google(root: Path, until: str, limit: int, offline: bool = False) -> dict:
    if not START <= until <= min(date.today().isoformat(), END) or limit < 0:
        raise ValueError("Google collection requires an in-scope cutoff and nonnegative limit")
    discovery = read_json(root / "data/raw/google-discovery.json", None)
    if discovery is None or discovery["until"] != until:
        discovery = discover_google(root, until)
    path = root / "data/site/google.json"
    snapshot = read_json(path, {"ads": [], "sources": []})
    ads = {ad["id"]: ad for ad in snapshot["ads"]}
    progress_path = root / "data/raw/google-progress.json"
    progress = read_json(progress_path, {"records": {}, "blocked": ""})
    client = Client(root / "data/raw/http", offline)
    count = 0

    def persist():
        snapshot["ads"] = sorted(ads.values(), key=lambda ad: (ad["published"], ad["id"]))
        snapshot["sources"] = [
            dict(
                source="google",
                url="https://adstransparency.google.com/political?region=US",
                state="partial",
                checked=date.today().isoformat(),
                last_success=until if ads else None,
                discovery_complete=False,
                bundle_updated=discovery["updated"],
                federal_video_and_image_leads=len(discovery["leads"]),
                attempted=len(progress["records"]),
                ads_with_text=len(ads),
                scope=discovery["scope"],
                blocked=progress["blocked"],
            )
        ]
        write_json(path, snapshot)
        write_json(progress_path, progress)

    if progress["blocked"] and not offline:
        print("Google collection remains blocked: " + progress["blocked"], flush=True)
        return snapshot
    for lead in coverage_order(discovery["leads"]):
        if (
            offline
            and not (root / "data/raw/google-creatives" / (lead["Ad_ID"] + ".json")).exists()
        ):
            continue
        if not offline and lead["Ad_ID"] in progress["records"]:
            continue
        if limit and count >= limit:
            break
        count += 1
        imported = []
        try:
            payload = creative_payload(root, lead, offline)
            start, end = us_delivery(lead, payload)
            if not in_window(start, end, until):
                raise ValueError("U.S. delivery outside scope")
            urls = preview_images(payload)
            for url in urls:
                body, _ = client.get(url, retry=False)
                image_hash, ocr = recognize_image(root / "data/media/google-images", body)
                ad = preview_ad(lead, payload, url, image_hash, ocr)
                prior = ads.get(ad["id"])
                if prior and prior["source_hash"] == ad["source_hash"]:
                    ad["observed"] = prior["observed"]
                ads[ad["id"]] = ad
                imported.append(ad["id"])
            progress["records"][lead["Ad_ID"]] = {
                "state": "text" if imported else "no_direct_image_preview",
                "ads": imported,
            }
        except HTTPError as error:
            progress["records"][lead["Ad_ID"]] = {"state": f"http_{error.code}"}
            if error.code in {401, 403, 429}:
                progress["blocked"] = f"HTTP {error.code}; no retries or alternate access methods"
                break
        except (OSError, ValueError, KeyError) as error:
            progress["records"][lead["Ad_ID"]] = {
                "state": "unprocessed",
                "detail": str(error),
                "ads": imported,
            }
        if count % 10 == 0:
            persist()
            print(f"Google: {count} records checked this run; {len(ads)} text previews", flush=True)
    persist()
    print(json.dumps(snapshot["sources"][0]), flush=True)
    return snapshot
