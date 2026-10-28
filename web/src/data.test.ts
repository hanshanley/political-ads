import { describe, expect, it } from "vitest";
import {
  csv, EMPTY_FILTERS, filterAds, monthlyCounts, observationDate, portrayalSummary, publisher,
  selectPortrayalEvidence, shares, type Ad, type Description,
} from "./data";

const base: Ad = {
  id: "", text: "", alignment: "D", message_id: "", published: "", chamber: "", race: "",
  source: "", sponsor_type: "", phase: "", issues: [], portrayal_markers: [], title: "",
  sponsor: "", source_url: "https://example.org/ad", observed: "2026-10-01", source_hash: "",
  text_hash: "", state: "", date_basis: "release_date", placement: "campaign_release",
  attribution_basis: "Test fixture", segments: [], media_urls: [], quality_flags: [],
};
const ads: Ad[] = [
  { ...base, id: "one", text: "Full health care\nmessage.", alignment: "D", message_id: "m",
    published: "2026-09-01", chamber: "House", state: "PA", race: "PA-10", source: "dccc",
    sponsor_type: "party", phase: "unknown", issues: [{ label: "Healthcare", text: "health care", start: 5, end: 16 }],
    portrayal_markers: [], title: "First ad", sponsor: "DCCC" },
  { ...base, id: "two", text: "Full health care\nmessage.", alignment: "D", message_id: "m",
    published: "2026-09-03", chamber: "House", state: "PA", race: "PA-10", source: "dccc",
    sponsor_type: "party", phase: "unknown", issues: [{ label: "Healthcare", text: "health care", start: 5, end: 16 }],
    portrayal_markers: [], title: "Mirrored ad", sponsor: "DCCC" },
  { ...base, id: "three", text: "=All the Republican text", alignment: "R", message_id: "r",
    published: "2026-10-01", chamber: "Senate", state: "NC", race: "NC-Senate", source: "nrsc",
    sponsor_type: "party", phase: "general", issues: [], portrayal_markers: [],
    title: "Third ad", sponsor: "NRSC" },
];

const description = (overrides: Partial<Description> = {}): Description => ({
  target: "Jane Republican", target_party: "R", target_kind: "person",
  target_role: "opponent", frame: "integrity", tone: "negative", voice: "advertiser",
  phrase: "cannot be trusted", quote: "Jane Republican cannot be trusted.",
  target_quote: "Jane Republican", start: 16, end: 33, target_start: 0, target_end: 15,
  ...overrides,
});
const reviewed = (ad: Ad, descriptions: Description[]): Ad => ({
  ...ad,
  portrayal_review: {
    status: "reviewed", ad_id: ad.id, source_hash: ad.source_hash, text_hash: ad.text_hash,
    reason: "", descriptions,
  },
});

describe("synchronized evidence", () => {
  it("applies every requested dimension without mutating the corpus", () => {
    expect(filterAds(ads, { ...EMPTY_FILTERS, query: "health care", party: "D", chamber: "House",
      state: "PA", race: "PA-10", source: "dccc", sponsorType: "party", phase: "unknown",
      issue: "Healthcare", start: "2026-09-02", end: "2026-09-30",
    }).map(ad => ad.id)).toEqual(["two"]);
    expect(ads).toHaveLength(3);
    expect(filterAds(ads, { ...EMPTY_FILTERS, phase: "primary" })).toEqual([]);
    expect(filterAds(ads, { ...EMPTY_FILTERS, state: "NC" }).map(ad => ad.id)).toEqual(["three"]);
  });

  describe("person portrayal summaries", () => {
    it("classifies mixed tone once while overlapping negative and positive shares", () => {
      const ad = reviewed(ads[0], [
        description(),
        description({ tone: "positive", frame: "competence", phrase: "an effective negotiator" }),
      ]);
      const result = portrayalSummary([ad], "opponents").D;
      expect(result.eligible).toBe(1);
      expect(result.tones).toEqual({
        "negative-only": 0, "positive-only": 0, mixed: 1, "neutral-only": 0,
      });
      expect([result.negative, result.positive]).toEqual([1, 1]);
      expect(result.frames).toEqual({ integrity: 1, competence: 1 });
    });

    it("excludes quoted, rebutted and same-party rival portrayals from cross-party totals", () => {
      const ad = reviewed({ ...ads[2], alignment: "R" }, [
        description({ target_party: "D", voice: "quoted_opponent" }),
        description({ target_party: "D", voice: "rebutted_claim" }),
        description({ target_party: "R", target: "A Republican rival" }),
      ]);
      const result = portrayalSummary([ad], "opponents").R;
      expect(result.coverage.reviewed).toBe(1);
      expect(result.eligible).toBe(0);
      expect(result.tones["neutral-only"]).toBe(0);
    });

    it("treats an absent review as unreviewed rather than neutral or zero-percent evidence", () => {
      const explicitlyUnreviewed: Ad = { ...ads[0], portrayal_review: {
        status: "unreviewed", text_hash: "", reason: "No review exists.", descriptions: [],
      } };
      const result = portrayalSummary([explicitlyUnreviewed], "opponents").D;
      expect(result.coverage).toEqual({ reviewed: 0, uncertain: 0, unreviewed: 1, stale: 0 });
      expect(result.eligible).toBe(0);
      expect(result.tones).toEqual({
        "negative-only": 0, "positive-only": 0, mixed: 0, "neutral-only": 0,
      });
    });

    it("deduplicates exact party messages after filtering and keeps zero denominators explicit", () => {
      const first = reviewed(ads[0], [description()]);
      const duplicate = reviewed(ads[1], [description()]);
      const result = portrayalSummary([first, duplicate], "opponents");
      expect(result.D.messages).toBe(1);
      expect(result.D.eligible).toBe(1);
      expect(result.D.tones["negative-only"]).toBe(1);
      expect(result.R.messages).toBe(0);
      expect(result.R.eligible).toBe(0);
    });

    it("uses supported-candidate role for self portrayals without admitting it to opponents", () => {
      const own = description({
        target: "Jane Democrat", target_party: "D", target_role: "self_or_supported",
        tone: "positive",
      });
      const ad = reviewed(ads[0], [own]);
      expect(portrayalSummary([ad], "self").D.tones["positive-only"]).toBe(1);
      expect(portrayalSummary([ad], "opponents").D.eligible).toBe(0);
    });

    it("selects deterministic evidence across common frames, messages and targets", () => {
      const evidence = [
        { adId: "a", description: description({ frame: "integrity", target: "One" }) },
        { adId: "b", description: description({ frame: "integrity", target: "Two" }) },
        { adId: "c", description: description({ frame: "integrity", target: "Three" }) },
        { adId: "d", description: description({ frame: "competence", target: "Four",
          tone: "positive" }) },
        { adId: "e", description: description({ frame: "competence", target: "Five" }) },
        { adId: "f", description: description({ frame: "connection", target: "Six",
          tone: "neutral" }) },
      ];
      const selected = selectPortrayalEvidence(evidence, 3);
      expect(selected.map(item => item.description.frame)).toEqual([
        "integrity", "competence", "connection",
      ]);
      expect(new Set(selected.map(item => item.adId)).size).toBe(3);
      expect(new Set(selected.map(item => item.description.target)).size).toBe(3);
      expect(selectPortrayalEvidence(evidence, 3)).toEqual(selected);
    });
  });
  it("deduplicates after filtering and distinguishes no evidence from zero matches", () => {
    const row = shares(ads, ["Healthcare"], "issues")[0];
    expect(row.D).toEqual({ count: 1, total: 1, value: 1 });
    expect(row.R).toEqual({ count: 0, total: 1, value: 0 });
    expect(shares(ads.slice(0, 2), ["Healthcare"], "issues")[0].R.value).toBeNull();
  });
  it("exports complete text and nested evidence, with formula protection", () => {
    const text = csv(ads);
    expect(text).toContain('"Full health care\nmessage."');
    expect(text).toContain("'=All the Republican text");
    expect(text).toContain('""label"":""Healthcare""');
    expect(text).toContain('"three"');
    expect(csv([{ ...ads[0], text: " \t=SUM(1,1)" }])).toContain("' \t=SUM(1,1)");
  });
  it("keeps unresolved and bipartisan publishers separate and outside party denominators", () => {
    const unresolved: Ad = { ...ads[0], id: "unresolved", alignment: "unknown", message_id: "u" };
    const bipartisan: Ad = { ...ads[0], id: "bipartisan", alignment: "other", message_id: "b",
      original_alignment: "unknown", alignment_review: {
        id: "program-2026", alignment: "other", status: "bipartisan", reviewed_on: "2026-10-27",
        rationale: "Documented cross-party program.", reviewed_source_hash: "",
        evidence: [{ url: "https://example.org/program" }],
      } };
    const corpus = [...ads, unresolved, bipartisan];
    expect(filterAds(corpus, { ...EMPTY_FILTERS, party: "unknown" })).toEqual([unresolved]);
    expect(filterAds(corpus, { ...EMPTY_FILTERS, party: "other" })).toEqual([bipartisan]);
    expect(shares(corpus, ["Healthcare"], "issues")).toEqual(shares(ads, ["Healthcare"], "issues"));
    expect(csv([unresolved])).toContain('"Full health care\nmessage."');
    expect(csv([bipartisan])).toContain('""status"":""bipartisan""');
    expect(csv([bipartisan])).toContain('"original_alignment"');
  });
  it("uses reported delivery overlap, including carryovers, without assuming launch dates", () => {
    const carryover: Ad = { ...ads[0], published: "2025-11-01", date_basis: "delivery",
      delivery_start: "2025-11-01", delivery_end: "2026-03-01" };
    expect(filterAds([carryover], EMPTY_FILTERS)).toEqual([carryover]);
    expect(filterAds([carryover], { ...EMPTY_FILTERS, start: "2026-04-01" })).toEqual([]);
    expect(observationDate(carryover)).toBe("2026-01-01");
    expect(observationDate(ads[0])).toBe("2026-09-01");
  });
  it("includes the final November 4 day but excludes November 5 by default", () => {
    const final = { ...ads[0], id: "final", published: "2026-11-04" };
    const after = { ...ads[0], id: "after", published: "2026-11-05" };
    expect(filterAds([final, after], EMPTY_FILTERS)).toEqual([final]);
  });
  it("groups a sponsor across acquisition IDs, matching backend publisher counts", () => {
    expect(publisher({ ...ads[0], source: "native-snap", sponsor: "Same payer" })).toBe("Same payer");
    expect(publisher({ ...ads[0], source: "native-google", sponsor: "Same payer" })).toBe("Same payer");
    expect(publisher({ ...ads[0], source: "native-snap", sponsor: "" })).toBe("native");
  });
  it("keeps real zero months without rendering unobserved future months as zeros", () => {
    const rows = monthlyCounts(ads, "2026-08-01", "2026-10-27");
    expect(rows).toEqual([
      { month: "2026-08", D: 0, R: 0 }, { month: "2026-09", D: 1, R: 0 },
      { month: "2026-10", D: 0, R: 1 },
    ]);
    expect(monthlyCounts([], "2026-11-01", "2026-10-27")).toEqual([]);
    const carryover = { ...ads[0], delivery_start: "2025-11-01" };
    expect(monthlyCounts([carryover], "2026-02-01", "2026-03-01")[0])
      .toEqual({ month: "2026-01", D: 1, R: 0 });
  });
});
