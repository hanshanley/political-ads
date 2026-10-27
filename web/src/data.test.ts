import { describe, expect, it } from "vitest";
import { csv, EMPTY_FILTERS, filterAds, observationDate, shares, type Ad } from "./data";

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
  it("retains unresolved publishers without adding them to either party's denominator", () => {
    const unresolved: Ad = { ...ads[0], id: "unresolved", alignment: "unknown", message_id: "u" };
    const corpus = [...ads, unresolved];
    expect(filterAds(corpus, { ...EMPTY_FILTERS, party: "unknown" })).toEqual([unresolved]);
    expect(shares(corpus, ["Healthcare"], "issues")).toEqual(shares(ads, ["Healthcare"], "issues"));
    expect(csv([unresolved])).toContain('"Full health care\nmessage."');
  });
  it("uses reported delivery overlap, including carryovers, without assuming launch dates", () => {
    const carryover: Ad = { ...ads[0], published: "2025-11-01", date_basis: "delivery",
      delivery_start: "2025-11-01", delivery_end: "2026-03-01" };
    expect(filterAds([carryover], EMPTY_FILTERS)).toEqual([carryover]);
    expect(filterAds([carryover], { ...EMPTY_FILTERS, start: "2026-04-01" })).toEqual([]);
    expect(observationDate(carryover)).toBe("2026-01-01");
    expect(observationDate(ads[0])).toBe("2026-09-01");
  });
});
