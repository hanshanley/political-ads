from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from zipfile import ZipFile

from bs4 import BeautifulSoup

from political_ads.cli import read_json, write_json
from political_ads.google import federal_advertisers
from political_ads.http import Client
from political_ads.images import recognize_image
from political_ads.registry import candidate_mentions
from political_ads.schema import END, START, Ad, digest, in_window
from political_ads.sources import language_of
from political_ads.video import recognize_video, video_segments

ARCHIVE = "snap-political-ads-2026.zip"
LIBRARY = "https://www.snap.com/political-ads/"


def federal_payer(row: dict, candidates: list[dict], names: dict, aliases: dict) -> dict | None:
    payer = row["PayingAdvertiserName"]
    key = payer.strip().casefold()
    declared = set(re.findall(r"\bC\d{8}\b", row["CommitteeIdentificationNumber"]))
    named = names.get(key, set())
    reviewed = aliases.get(key)
    if reviewed and reviewed.get("landing_hosts"):
        landing = re.search(r"https?://[^\s,;]+", row.get("CreativeProperties", ""))
        host = urlsplit(landing[0]).hostname if landing else ""
        if not host or host.removeprefix("www.") not in reviewed["landing_hosts"]:
            return None
    if reviewed and "publisher" in reviewed:
        committee_id = reviewed.get("committee_id", "")
        disclosure_id = reviewed.get("noncommittee_disclosure_id", "")
        disclosure_ids = reviewed.get("noncommittee_disclosure_ids", [])
        allowed = {
            identity for identity in [committee_id, disclosure_id, *disclosure_ids] if identity
        }
        if (declared | named) - allowed:
            return None
        return (
            reviewed["publisher"]
            | {
                "committee_id": committee_id,
                "noncommittee_disclosure_id": disclosure_id,
                "payer": payer,
                "identity_basis": reviewed["evidence"],
                "identity_url": reviewed["evidence_url"],
                "requires_federal_mention": True,
            }
            | ({"noncommittee_disclosure_ids": disclosure_ids} if disclosure_ids else {})
        )
    identities = declared | named | ({reviewed["committee_id"]} if reviewed else set())
    if len(identities) != 1:
        return None
    committee = next(iter(identities))
    reviewed_candidate = reviewed.get("candidate_id") if reviewed else None
    if reviewed_candidate:
        candidates = [
            candidate
            for candidate in candidates
            if candidate["candidate_id"] == reviewed_candidate
            and candidate["principal_committee"] == committee
        ]
        if len(candidates) != 1:
            return None
    matched = federal_advertisers(
        [dict(Advertiser_ID=payer, Advertiser_Name=payer, Public_IDs_List=committee)], candidates
    ).get(payer)
    if matched is None:
        return None
    if declared:
        basis = f"Snap reports FEC committee ID {committee}."
        evidence_url = LIBRARY
    elif named:
        basis = f"Exact case-insensitive payer/legal-name join to FEC committee {committee}."
        evidence_url = f"https://www.fec.gov/data/committee/{committee}/"
    else:
        basis = reviewed["evidence"]
        evidence_url = reviewed["evidence_url"]
    if reviewed_candidate:
        basis += " " + reviewed["evidence"] + " " + reviewed["evidence_url"]
    return matched | {"payer": payer, "identity_basis": basis, "identity_url": evidence_url}


def asset_identity(url: str) -> tuple[str, str]:
    parsed = urlsplit(url)
    match = re.fullmatch(r"/political-ads/asset/([a-f0-9]{64})", parsed.path)
    kinds = parse_qs(parsed.query).get("mediaType", [])
    if (
        parsed.scheme != "https"
        or parsed.hostname != "www.snap.com"
        or not match
        or len(kinds) != 1
        or kinds[0] not in {"png", "jpg", "jpeg", "mp4"}
    ):
        raise ValueError("Unsupported native Snap creative URL")
    return match[1], kinds[0]


def native_asset(html: bytes, viewer_url: str) -> str:
    identity, kind = asset_identity(viewer_url)
    expected = (
        f"https://storage.googleapis.com/ad-manager-political-ads-dump-shadow/{identity}.{kind}"
    )
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("video" if kind == "mp4" else "img", src=expected)
    if tag is None:
        raise ValueError("No matching original creative in Snap's public asset viewer")
    return tag["src"]


def snap_leads(
    rows: list[dict],
    candidates: list[dict],
    committees: list[dict],
    aliases: dict,
    until: str,
    rejected: list[dict] | None = None,
    unmatched: list[dict] | None = None,
) -> list[dict]:
    names = defaultdict(set)
    for committee in committees:
        names[committee["name"].strip().casefold()].add(committee["committee_id"])
    aliases = {key.strip().casefold(): value for key, value in aliases.items()}
    groups = {}
    unmatched_groups = {}
    for row in rows:
        if row["CountryCode"].strip().casefold() != "united states":
            continue
        if float(row["Impressions"] or 0) <= 0:
            continue
        publisher = federal_payer(row, candidates, names, aliases)
        if publisher is None:
            if unmatched is not None:
                start = row["StartDate"][:10].replace("/", "-")
                end = row["EndDate"][:10].replace("/", "-") or None
                try:
                    eligible = in_window(start, end, until)
                except ValueError:
                    eligible = False
                if eligible:
                    payer = row["PayingAdvertiserName"]
                    group = unmatched_groups.setdefault(
                        payer,
                        dict(
                            payer=payer,
                            review_state=(
                                "reviewed_alias_constraints_not_met"
                                if payer.strip().casefold() in aliases
                                else "unreviewed_identity_and_scope"
                            ),
                            platform_ad_ids=set(),
                            creative_urls=set(),
                            reported_fec_ids=set(),
                            landing_hosts=set(),
                            candidate_ballot_information=set(),
                        ),
                    )
                    group["platform_ad_ids"].add(row["ADID"])
                    group["creative_urls"].add(row["CreativeUrl"])
                    group["reported_fec_ids"].update(
                        re.findall(r"\bC\d{8}\b", row["CommitteeIdentificationNumber"])
                    )
                    landing = re.search(r"https?://[^\s,;]+", row.get("CreativeProperties", ""))
                    if landing and (host := urlsplit(landing[0]).hostname):
                        group["landing_hosts"].add(host)
                    if information := row.get("CandidateBallotInformation", "").strip():
                        group["candidate_ballot_information"].add(information)
            continue
        start = row["StartDate"][:10].replace("/", "-")
        end = row["EndDate"][:10].replace("/", "-") or None
        try:
            if not in_window(start, end, until):
                continue
            identity, kind = asset_identity(row["CreativeUrl"])
        except ValueError as error:
            if rejected is not None:
                rejected.append(
                    dict(
                        ad_id=row["ADID"],
                        source_url=row["CreativeUrl"],
                        payer=row["PayingAdvertiserName"],
                        start=start,
                        end=end,
                        reason=str(error),
                    )
                )
            continue
        key = (publisher["committee_id"] or publisher["source"], identity)
        lead = groups.setdefault(
            key,
            dict(
                id="snap-" + digest("\n".join(key))[:24],
                source_url=row["CreativeUrl"],
                asset_id=identity,
                media_type=kind,
                publisher=publisher,
                placements=[],
            ),
        )
        if lead["media_type"] != kind:
            raise ValueError("Snap creative identity has conflicting media types")
        lead["placements"].append(
            dict(
                ad_id=row["ADID"],
                scheduled_start=start,
                scheduled_end=end,
                payer=row["PayingAdvertiserName"],
                positive_impressions=True,
            )
        )
    if unmatched is not None:
        unmatched.extend(
            {
                key: sorted(value) if isinstance(value, set) else value
                for key, value in group.items()
            }
            for _, group in sorted(unmatched_groups.items())
        )
    return sorted(groups.values(), key=lambda lead: (lead["publisher"]["source"], lead["id"]))


def discover_snap(root: Path, until: str) -> dict:
    registry = read_json(root / "data/processed/registry.json", {})
    archive_path = root / "data/raw" / ARCHIVE
    with ZipFile(archive_path) as archive:
        with archive.open("PoliticalAds.csv") as handle:
            rows = list(csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8-sig")))
    rejected = []
    unmatched = []
    leads = snap_leads(
        rows,
        registry["candidates"],
        registry["committees"],
        read_json(root / "data/snap-payers.json", {}),
        until,
        rejected,
        unmatched,
    )
    result = dict(
        until=until,
        archive_sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        rows_scanned=len(rows),
        rejected_federal_records=rejected,
        unmatched_payers=unmatched,
        leads=leads,
    )
    write_json(root / "outputs/snap-discovery.json", result)
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key not in {"leads", "unmatched_payers"}
            }
            | dict(
                unmatched_payer_count=len(unmatched),
                unmatched_payer_creatives=sum(len(payer["creative_urls"]) for payer in unmatched),
                candidate_creatives=len(leads),
                federal_scope_pending=sum(
                    bool(lead["publisher"].get("requires_federal_mention")) for lead in leads
                ),
                platform_ad_records=sum(len(lead["placements"]) for lead in leads),
                by_party=dict(Counter(lead["publisher"]["alignment"] for lead in leads)),
                by_type=dict(Counter(lead["media_type"] for lead in leads)),
            )
        ),
        flush=True,
    )
    return result


def snap_ad(
    lead: dict,
    media_hash: str,
    ocr: dict,
    speech: dict | None = None,
    candidates: list[dict] | None = None,
    scope_review: dict | None = None,
) -> dict:
    publisher = lead["publisher"]
    if speech is not None:
        segments = video_segments(ocr, speech, media_hash)
    else:
        if ocr.get("image_frame_count", 1) != 1:
            raise ValueError("Animated Snap images require complete frame extraction")
        segments = [
            dict(
                text=line["text"],
                kind="image_ocr",
                voice="unreviewed",
                start_seconds=None,
                end_seconds=None,
                confidence=line["confidence"],
                image_bounds=line["bounds"],
                image_hash=media_hash,
                coordinate_system=ocr["coordinate_system"],
                extraction_engine=ocr["engine"],
            )
            for line in ocr["lines"]
            if line["text"].strip()
        ]
    text = "\n".join(segment["text"] for segment in segments)
    if not text or re.fullmatch(r"paid for by[^\n]*", text, re.I):
        raise ValueError("No substantive Snap creative text")
    source_hash = digest(json.dumps([lead, media_hash, ocr, speech], sort_keys=True))
    if publisher.get("requires_federal_mention"):
        roster = [
            c
            for c in candidates or []
            if c["office"] in {"H", "S"} and c["election_year"] == "2026"
        ]
        contexts = [
            (
                "speech",
                None,
                " ".join(segment["text"] for segment in segments if segment["kind"] == "local_asr"),
            )
        ]
        frames = ocr.get("frames", [{"seconds": None, "lines": ocr.get("lines", [])}])
        contexts.extend(
            (
                "frame",
                frame["seconds"],
                " ".join(line["text"] for line in frame["lines"] if line["confidence"] >= 0.8),
            )
            for frame in frames
        )
        evidence = [
            {"lane": lane, "seconds": seconds, "text": context, "candidate_mentions": mentions}
            for lane, seconds, context in contexts
            if (mentions := candidate_mentions(context, roster))
        ]
        if scope_review:
            if scope_review["source_hash"] != source_hash:
                raise ValueError(
                    "Snap federal-scope review does not match the extracted source hash"
                )
            if not scope_review["quotes"] or not all(q in text for q in scope_review["quotes"]):
                raise ValueError("Snap federal-scope review quotes must occur in recovered text")
            by_id = {c["candidate_id"]: c for c in roster if not c.get("reviewed_alias")}
            if not scope_review["candidate_ids"] or any(
                candidate_id not in by_id for candidate_id in scope_review["candidate_ids"]
            ):
                raise ValueError(
                    "Snap federal-scope review requires actual 2026 federal candidates"
                )
            evidence.append(
                {
                    "lane": "reviewed_identity",
                    "review": scope_review,
                    "candidate_mentions": [
                        {
                            key: by_id[candidate_id][key]
                            for key in (
                                "candidate_id",
                                "name",
                                "party",
                                "state",
                                "office",
                                "district",
                            )
                        }
                        for candidate_id in scope_review["candidate_ids"]
                    ],
                }
            )
        if not evidence:
            raise ValueError("Reviewed advocacy payer: no full 2026 federal candidate name in text")
        aliases = {
            (c["candidate_id"], c["name"]): c["reviewed_alias"]
            for c in roster
            if c.get("reviewed_alias")
        }
        for item in evidence:
            for mention in item["candidate_mentions"]:
                alias = aliases.get((mention["candidate_id"], mention["name"]))
                if alias:
                    mention["reviewed_alias"] = alias
        segments[0]["federal_scope_evidence"] = evidence
        races = {
            (m["state"], m["office"], m["district"])
            for item in evidence
            for m in item["candidate_mentions"]
        }
        if len(races) == 1:
            state, office, district = races.pop()
            publisher = publisher | {
                "state": state,
                "chamber": "House" if office == "H" else "Senate",
                "race": f"{state}-{int(district):02}" if office == "H" else f"{state}-Senate",
            }
    segments[0].update(
        snap_ad_ids=sorted({p["ad_id"] for p in lead["placements"]}),
        snap_placements=lead["placements"],
        snap_asset_id=lead["asset_id"],
        fec_committee_id=publisher["committee_id"] or None,
        fec_noncommittee_disclosure_id=publisher.get("noncommittee_disclosure_id") or None,
        payer_identity_basis=publisher["identity_basis"],
        federal_scope_requires_candidate_mention=bool(publisher.get("requires_federal_mention")),
        reported_platform="snap",
        reported_ad_type="video" if speech is not None else "image",
    )
    if publisher.get("noncommittee_disclosure_ids"):
        segments[0]["fec_noncommittee_disclosure_ids"] = publisher["noncommittee_disclosure_ids"]
    start = min(p["scheduled_start"] for p in lead["placements"])
    ends = [p["scheduled_end"] for p in lead["placements"]]
    end = max(ends) if all(ends) else None
    language = language_of(text)
    if speech and any(segment["kind"] == "local_asr" for segment in segments):
        language = speech["language"] if speech["language_probability"] >= 0.9 else "unknown"
    return Ad(
        id=lead["id"],
        source=publisher["source"] + "-snap",
        source_url=lead["source_url"],
        source_record_id=lead["asset_id"],
        title=f"Snap {segments[0]['reported_ad_type']} ad",
        sponsor=publisher["sponsor"],
        sponsor_type=publisher["sponsor_type"],
        alignment=publisher["alignment"],
        published=start,
        observed=date.today().isoformat(),
        text=text,
        segments=segments,
        source_hash=source_hash,
        date_basis="scheduled_delivery",
        delivery_start=start,
        delivery_end=end,
        placement="snap_paid_ad_scheduled_dates",
        race=publisher["race"],
        state=publisher["state"],
        chamber=publisher["chamber"],
        language=language,
        language_basis=(
            "Multilingual local Whisper language detection when speech is present; "
            "otherwise seeded detection of local English OCR. Uncertain speech excluded."
        ),
        media_urls=[lead["source_url"]],
        quality_flags=[
            "machine_extraction_not_independently_reviewed",
            "snap_dates_are_scheduled_not_verified_daily_delivery",
            "positive_impressions_do_not_locate_delivery_within_scheduled_interval",
            "creative_placement_intervals_not_continuous_delivery",
        ]
        + (
            ["implausible_asr_timing_excluded_retained_for_review"]
            if segments[0].get("excluded_implausible_asr_segments")
            else []
        )
        + (
            [
                "local_asr_may_misrecognize_words",
                "video_frame_sampling_may_miss_short_overlays",
                "video_speech_and_on_screen_are_separate_lanes",
            ]
            if speech is not None
            else ["image_ocr_may_misrecognize_words", "image_reading_order_unverified"]
        ),
        attribution_basis=(
            publisher["identity_basis"]
            + " "
            + publisher["identity_url"]
            + ". "
            + (
                (
                    "Reviewed advocacy payer with an evidenced FEC committee ID. "
                    if publisher["committee_id"]
                    else "Reviewed advocacy payer without an assigned FEC committee ID; "
                    "evidenced noncommittee disclosure IDs are retained separately. "
                    if publisher.get("noncommittee_disclosure_ids")
                    else "Reviewed advocacy payer without an assigned FEC committee ID; "
                    "an evidenced noncommittee disclosure ID is retained separately. "
                    if publisher.get("noncommittee_disclosure_id")
                    else "Reviewed advocacy payer without an assigned FEC committee ID; "
                    "no noncommittee disclosure ID is assigned in this crosswalk. "
                )
                + "Recovered text must "
                "contain a full 2026 House/Senate candidate name or an exact-source-hash-bound "
                "federal-identity review with quoted evidence. Alignment is organizational, "
                "not inferred from hostile wording. A single mentioned race is context, "
                "not a validated target assignment. "
                if publisher.get("requires_federal_mention")
                else "FEC identity mapped to an unambiguous 2026 federal principal committee "
                "or reviewed federal publisher. Race is the sponsor's seat, "
                "not an inferred target. "
            )
            + "Official Snap 2026 archive reports positive impressions for these ad IDs; "
            "dates are scheduled starts/stops, not independently verified delivery days. "
            "Repeated ad IDs sharing a payer and asset are one creative record. "
            "Machine-recognized speech and distinct on-screen text are separate evidence "
            "lanes, not a single certified utterance; repeated speech/subtitles are deduplicated."
        ),
    ).to_dict()


def apply_language_review(ad: dict, ledger: dict) -> dict:
    approved = ledger.get("english_source_hashes", {}).get(ad["id"])
    if approved:
        if approved != ad["source_hash"]:
            raise ValueError("Snap language review does not match the extracted source hash")
        ad["segments"][0]["language_review"] = {
            "automatic_language": ad["language"],
            "source_hash": approved,
            "basis": ledger["basis"],
        }
        ad["language"] = "en"
        ad["language_basis"] = ledger["basis"]
    return ad


def collect_snap(
    root: Path,
    until: str,
    limit: int = 0,
    offline: bool = False,
) -> dict:
    if not START <= until <= min(date.today().isoformat(), END) or limit < 0:
        raise ValueError("Snap collection requires an in-scope cutoff and nonnegative limit")
    discovery = read_json(root / "outputs/snap-discovery.json", None)
    if discovery is None or discovery["until"] != until:
        discovery = discover_snap(root, until)
    path = root / "data/site/snap.json"
    snapshot = read_json(path, {"ads": [], "sources": []})
    ads = {ad["id"]: ad for ad in snapshot["ads"]}
    progress_path = root / "data/raw/snap-progress.json"
    progress = read_json(progress_path, {"records": {}, "blocked": ""})
    client = Client(root / "data/raw/http", offline)
    candidates = read_json(root / "data/processed/registry.json", {}).get("candidates", [])
    by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
    for alias in read_json(root / "data/snap-candidate-aliases.json", []):
        if alias["candidate_id"] in by_id:
            candidates.append(
                by_id[alias["candidate_id"]]
                | {
                    "name": alias["name"],
                    "reviewed_alias": alias,
                }
            )
    language_reviews = read_json(root / "data/snap-language-reviews.json", {})
    scope_reviews = read_json(root / "data/snap-scope-reviews.json", {})

    def persist():
        snapshot["ads"] = sorted(ads.values(), key=lambda ad: (ad["published"], ad["id"]))
        snapshot["sources"] = [
            dict(
                source="snap",
                url=LIBRARY,
                state="partial",
                checked=date.today().isoformat(),
                last_success=until if ads else None,
                discovery_complete=False,
                archive_sha256=discovery["archive_sha256"],
                candidate_creatives=len(discovery["leads"]),
                federal_scope_pending=sum(
                    bool(lead["publisher"].get("requires_federal_mention"))
                    and lead["id"] not in ads
                    for lead in discovery["leads"]
                ),
                platform_ad_records=sum(len(lead["placements"]) for lead in discovery["leads"]),
                attempted=len(progress["records"]),
                ads_with_text=len(ads),
                blocked=progress["blocked"],
                scope="U.S. positive-impression 2026 archive records with in-window scheduled "
                "dates; "
                "exact FEC IDs, exact FEC legal-name joins and explicitly reviewed payer aliases; "
                "advocacy payers without FEC IDs require a full 2026 federal candidate name "
                "or a hash-bound reviewed federal identity in recovered text. "
                "Not every advertiser; scheduled dates are not verified daily delivery.",
            )
        ]
        write_json(path, snapshot)
        write_json(progress_path, progress)

    if progress["blocked"] and not offline:
        print("Snap collection remains blocked: " + progress["blocked"], flush=True)
        return snapshot
    # Images first, then round-robin publishers so partial runs do not consume one payer only.
    ordered = []
    for video in (False, True):
        groups = defaultdict(list)
        for lead in discovery["leads"]:
            if (lead["media_type"] == "mp4") == video:
                groups[lead["publisher"]["source"]].append(lead)
        while groups:
            ordered.extend(group.pop(0) for _, group in sorted(groups.items()))
            groups = {key: group for key, group in groups.items() if group}
    count = 0
    for lead in ordered:
        if not offline and lead["id"] in progress["records"]:
            continue
        if offline and progress["records"].get(lead["id"], {}).get("state") not in {
            "text",
            "unprocessed",
        }:
            continue
        if limit and count >= limit:
            break
        count += 1
        extraction_ready = False
        try:
            html, _ = client.get(lead["source_url"], retry=False)
            url = native_asset(html, lead["source_url"])
            body, _ = client.get(url, retry=False)
            if lead["media_type"] == "mp4":
                media_hash, ocr, speech = recognize_video(root, body, offline)
                extraction_ready = True
                ad = snap_ad(
                    lead,
                    media_hash,
                    ocr,
                    speech,
                    candidates,
                    scope_review=scope_reviews.get(lead["id"]),
                )
            else:
                media_hash, ocr = recognize_image(root / "data/media/snap-images", body)
                extraction_ready = True
                ad = snap_ad(
                    lead,
                    media_hash,
                    ocr,
                    candidates=candidates,
                    scope_review=scope_reviews.get(lead["id"]),
                )
            ad = apply_language_review(ad, language_reviews)
            prior = ads.get(ad["id"])
            if prior and prior["source_hash"] == ad["source_hash"]:
                ad["observed"] = prior["observed"]
            ads[ad["id"]] = ad
            progress["records"][lead["id"]] = {"state": "text", "ad": ad["id"]}
        except HTTPError as error:
            progress["records"][lead["id"]] = {"state": f"http_{error.code}"}
            if error.code in {401, 403, 429}:
                progress["blocked"] = f"HTTP {error.code}; no retries or alternate access methods"
                break
        except (OSError, ValueError, KeyError) as error:
            if extraction_ready and isinstance(error, ValueError):
                ads.pop(lead["id"], None)
            progress["records"][lead["id"]] = {"state": "unprocessed", "detail": str(error)}
        if count % 5 == 0:
            persist()
            print(f"Snap: {count} creatives checked this run; {len(ads)} with text", flush=True)
    persist()
    print(json.dumps(snapshot["sources"][0]), flush=True)
    return snapshot
