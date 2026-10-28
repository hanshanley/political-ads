export type Party = "D" | "R" | "other" | "unknown";
export interface Match { label: string; text: string; start: number; end: number }
export interface Ad {
  id: string; source: string; source_url: string; title: string; sponsor: string;
  sponsor_type: string; alignment: Party; published: string; observed: string;
  text: string; message_id: string; source_hash: string; text_hash: string;
  race: string; state: string; chamber: string; phase: string; date_basis: string;
  delivery_start?: string | null; delivery_end?: string | null;
  placement: string; attribution_basis: string; issues: Match[]; portrayal_markers: Match[];
  segments: { text: string; kind: string; voice: string; start_seconds: number | null }[];
  media_urls: string[];
  quality_flags: string[];
  original_alignment?: Party;
  alignment_review?: {
    id: string; alignment: Party; status: string; rationale: string; reviewed_on: string;
    reviewed_source_hash: string; evidence: { url: string }[];
  };
}
export interface Example {
  ad_id: string; party: Party; target: string; target_party: Party; frame: string;
  quote: string; context: string; voice: string; purpose: string; source_url: string;
  start: number; end: number; race: string;
}
export interface Source {
  source: string; url: string; state: string; checked: string; last_success: string | null;
  posts_scanned: number; ads_with_text: number; error?: string; languages?: Record<string, number>;
}
export interface Dataset {
  snapshot_id: string; until: string; first_release: string; latest_release: string;
  ads: Ad[]; examples: Example[]; sources: Source[]; methodology: string[];
  codebook: { version: string; description: string; issues: Record<string, string[]>;
    portrayal_language: Record<string, string[]> };
  validation: { reviewed_examples: number; semantic_classifier: string;
    independent_human_gold: boolean };
}
export interface Filters {
  query: string; party: string; chamber: string; state: string; race: string; source: string;
  sponsorType: string; phase: string; issue: string; start: string; end: string;
}
export const EMPTY_FILTERS: Filters = {
  query: "", party: "", chamber: "", state: "", race: "", source: "", sponsorType: "",
  phase: "", issue: "", start: "2026-01-01", end: "2026-11-04",
};

export function filterAds(ads: Ad[], filters: Filters): Ad[] {
  const query = filters.query.toLocaleLowerCase().trim();
  return ads.filter(ad =>
    (!query || `${ad.text} ${ad.title} ${ad.sponsor} ${ad.race}`.toLocaleLowerCase().includes(query)) &&
    (!filters.party || ad.alignment === filters.party) &&
    (!filters.chamber || ad.chamber === filters.chamber) &&
    (!filters.state || ad.state === filters.state) &&
    (!filters.race || ad.race === filters.race) &&
    (!filters.source || ad.source === filters.source) &&
    (!filters.sponsorType || ad.sponsor_type === filters.sponsorType) &&
    (!filters.phase || ad.phase === filters.phase) &&
    (!filters.issue || ad.issues.some(match => match.label === filters.issue)) &&
    (!filters.start || (ad.delivery_start ?
      !ad.delivery_end || ad.delivery_end >= filters.start : ad.published >= filters.start)) &&
    (!filters.end || (ad.delivery_start || ad.published) <= filters.end),
  );
}

export function uniqueMessages(ads: Ad[]): Ad[] {
  const seen = new Set<string>();
  return [...ads].sort((a, b) => observationDate(a).localeCompare(observationDate(b)) ||
    a.id.localeCompare(b.id))
    .filter(ad => {
      const key = `${ad.alignment}:${ad.message_id}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

export function shares(ads: Ad[], labels: string[], field: "issues" | "portrayal_markers") {
  const unique = uniqueMessages(ads);
  return labels.map(label => ({
    label,
    ...Object.fromEntries((["D", "R"] as const).map(party => {
      const scope = unique.filter(ad => ad.alignment === party);
      const matching = scope.filter(ad => ad[field].some(match => match.label === label));
      return [party, { count: matching.length, total: scope.length,
        value: scope.length ? matching.length / scope.length : null }];
    })) as Record<"D" | "R", { count: number; total: number; value: number | null }>,
  })).sort((a, b) => (b.D.value ?? 0) + (b.R.value ?? 0) - (a.D.value ?? 0) - (a.R.value ?? 0));
}

export function csv(ads: Ad[]): string {
  if (!ads.length) return "id,text\r\n";
  const keys = [...new Set(ads.flatMap(ad => Object.keys(ad)))] as (keyof Ad)[];
  const cell = (value: unknown) => {
    let text = typeof value === "object" ? JSON.stringify(value) : String(value ?? "");
    if (/^\s*[=+\-@]/.test(text)) text = "'" + text;
    return `"${text.replaceAll('"', '""')}"`;
  };
  return [keys.map(cell).join(","), ...ads.map(ad => keys.map(key => cell(ad[key])).join(","))]
    .join("\r\n");
}

export function saveFile(name: string, contents: string, type: string) {
  const url = URL.createObjectURL(new Blob([contents], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const partyName = (party: string) => party === "D" ? "Democratic" :
  party === "R" ? "Republican" : party;
export const observationDate = (ad: Ad) => ad.delivery_start ?
  (ad.delivery_start < "2026-01-01" ? "2026-01-01" : ad.delivery_start) : ad.published;
export const publisher = (ad: Ad) => ad.sponsor || ad.source.replace(/-(media|images|google|snap)$/, "");

export function monthlyCounts(ads: Ad[], start: string, until: string) {
  const messages = uniqueMessages(ads).filter(ad => ad.alignment === "D" || ad.alignment === "R");
  const first = [start || "2026-01-01", ...messages.map(observationDate)].sort()[0];
  if (first > until) return [];
  const firstMonth = Number(first.slice(5, 7));
  const lastMonth = Number(until.slice(5, 7));
  const counts = Array.from({ length: lastMonth - firstMonth + 1 }, (_, index) => ({
    month: `2026-${String(firstMonth + index).padStart(2, "0")}`, D: 0, R: 0,
  }));
  for (const ad of messages) {
    const row = counts.find(row => row.month === observationDate(ad).slice(0, 7));
    if (row && (ad.alignment === "D" || ad.alignment === "R")) row[ad.alignment]++;
  }
  return counts;
}
export const displayDate = (value: string) => new Date(value + "T12:00:00Z")
  .toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
