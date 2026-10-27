import { StrictMode, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  type Ad, type Dataset, type Filters, EMPTY_FILTERS, csv, displayDate, filterAds,
  observationDate, partyName, publisher, saveFile, shares, uniqueMessages,
} from "./data";
import "./style.css";

function Select({ label, value, options, onChange }: {
  label: string; value: string; options: [string, string][]; onChange: (value: string) => void;
}) {
  return <label className="select-label">{label}<select aria-label={label} value={value}
    onChange={event => onChange(event.target.value)}>
    <option value="">All {label.toLowerCase()}</option>
    {options.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
  </select></label>;
}

function BarComparison({ ads, labels, field, onSelect }: {
  ads: Ad[]; labels: string[]; field: "issues" | "portrayal_markers";
  onSelect?: (label: string) => void;
}) {
  const rows = shares(ads, labels, field);
  return <div className="comparison">
    <div className="legend"><span className="D">Democratic</span><span className="R">Republican</span></div>
    <div className="chart-rows">
      {rows.map(row => <div className="chart-row" key={row.label}>
        {onSelect ? <button className="chart-label" onClick={() => onSelect(row.label)}>
          {row.label}</button> : <span className="chart-label">{row.label}</span>}
        <div className="bars">{(["D", "R"] as const).map(party =>
          <div key={party} className={`bar-line ${party}`} title={
            `${partyName(party)}: ${row[party].count} / ${row[party].total} unique messages`
          }>
            <div className="bar-track"><div className="bar"
              style={{ width: `${(row[party].value ?? 0) * 100}%` }} /></div>
            <span>{row[party].value === null ? "—" : `${Math.round(row[party].value * 100)}%`}</span>
            <span className="bar-count">{row[party].count}/{row[party].total}</span>
          </div>)}</div>
      </div>)}
    </div>
    <p className="chart-caption">Share of unique messages with a phrase-family match.
      Counts shown as matched / included. Categories overlap; no text in scope is not a zero.</p>
    <details className="data-table"><summary>View exact chart values</summary><table>
      <caption>Phrase-family matches per unique message</caption>
      <thead><tr><th>Language family</th><th>Democratic</th><th>Republican</th></tr></thead>
      <tbody>{rows.map(row => <tr key={row.label}><th>{row.label}</th>
        <td>{row.D.count} / {row.D.total || "no messages"}</td>
        <td>{row.R.count} / {row.R.total || "no messages"}</td></tr>)}</tbody>
    </table></details>
  </div>;
}

function Timeline({ ads }: { ads: Ad[] }) {
  const counts = Array.from({ length: 12 }, (_, month) => ({
    month: new Date(Date.UTC(2026, month, 1)).toLocaleDateString("en", { month: "short" }),
    D: 0, R: 0,
  }));
  for (const ad of uniqueMessages(ads)) {
    if (ad.alignment === "D" || ad.alignment === "R") {
      counts[Number(observationDate(ad).slice(5, 7)) - 1][ad.alignment]++;
    }
  }
  const highest = Math.max(1, ...counts.flatMap(row => [row.D, row.R]));
  return <div className="timeline-wrap">
    <svg viewBox="0 0 650 180" className="timeline" role="img"
      aria-labelledby="timeline-title timeline-description">
      <title id="timeline-title">Observed ad messages by month</title>
      <desc id="timeline-description">First release, in-scope Google delivery or Snap scheduled-start month.
        Pre-2026 carryovers are anchored to January, not new launches.
        Exact counts are available below. Not airing volumes.</desc>
      {[0, 0.5, 1].map(tick => <g key={tick}>
        <line x1="25" x2="640" y1={145 - tick * 120} y2={145 - tick * 120} stroke="#e1e3df" />
        <text x="0" y={150 - tick * 120} className="axis">{Math.round(tick * highest)}</text>
      </g>)}
      {counts.map((row, index) => <g key={row.month}>
        {(["D", "R"] as const).map((party, offset) => <rect key={party}
          x={35 + index * 50 + offset * 15} y={145 - row[party] / highest * 120}
          height={row[party] / highest * 120} width="12" className={`fill-${party}`}>
          <title>{row.month}: {partyName(party)} {row[party]} unique messages</title>
        </rect>)}
        <text x={46 + index * 50} y="170" textAnchor="middle" className="axis">{row.month}</text>
      </g>)}
    </svg>
    <details className="data-table"><summary>Monthly observed-message counts</summary><table>
      <caption>First release, reported delivery or scheduled start; not launches or airing totals</caption>
      <thead><tr><th>Month</th><th>Democratic</th><th>Republican</th></tr></thead>
      <tbody>{counts.map(row => <tr key={row.month}><th>{row.month}</th>
        <td>{row.D}</td><td>{row.R}</td></tr>)}</tbody>
    </table></details>
  </div>;
}

function AdCard({ ad, selected, examples }: {
  ad: Ad; selected: boolean; examples: Dataset["examples"];
}) {
  const [expanded, setExpanded] = useState(selected);
  const open = expanded;
  const annotations = examples.filter(example => example.ad_id === ad.id);
  return <article className={`ad-card ${selected ? "selected" : ""}`} id={`ad-${ad.id}`}>
    <div className="ad-meta"><span className={`party-dot ${ad.alignment}`}>
      {partyName(ad.alignment)}</span><span>{ad.race}</span><span>{displayDate(ad.published)}</span></div>
    <h3>{ad.title}</h3>
    <p className="publisher">{ad.sponsor} · {ad.sponsor_type.replace("_", " ")} publisher</p>
    <div className={`transcript ${open ? "open" : ""}`}>{ad.text}</div>
    <button className="text-button" aria-expanded={open} onClick={() => setExpanded(!open)}>
      {open ? "Show less" : "Read all available text"}</button>
    {annotations.map(example => <aside className="context-note" key={example.quote}>
      <strong>{example.frame} · {example.target}</strong><p>{example.context}</p>
    </aside>)}
    {open && <div className="provenance">
      <p><strong>{ad.alignment_review ? "Original acquisition attribution:" : "Attribution:"}</strong> {ad.attribution_basis}</p>
      {ad.alignment_review && <div>
        <p><strong>Reviewed publisher alignment ({ad.alignment_review.reviewed_on}):</strong>{" "}
          {ad.alignment_review.rationale} This supersedes the original alignment only.</p>
        <p>{ad.alignment_review.evidence.map((item, index) =>
          <span key={index}>{index > 0 && " · "}<a href={item.url} target="_blank" rel="noreferrer">
            Alignment source {index + 1}</a></span>)}</p>
      </div>}
      <p><strong>Text:</strong> {ad.segments[0]?.kind === "publisher_transcript" ?
        "Publisher transcript." : ad.segments[0]?.kind === "publisher_ad_copy" ?
          "Publisher-quoted ad copy; completeness is unverified." :
          ad.segments[0]?.kind === "image_ocr" ?
          "Local image-ad OCR; words and reading order may be imperfect. Image hashes and text coordinates are in the download." :
          ad.segments.some(segment => ["local_asr", "video_ocr"].includes(segment.kind)) ?
          "Local machine speech recognition and sampled-frame OCR, not a certified transcript. Speech and novel overlays are separate evidence lanes; timings, quality notes and duplicate evidence are in the download." :
          "Public video captions, with cue timestamps in the download."}
        {" "}Quotations and speaker labels are retained;
        this is not independent verification of what a quoted person actually said.</p>
      {ad.quality_flags?.length > 0 && <p><strong>Extraction notes:</strong> {
        ad.quality_flags.map(flag => flag.replaceAll("_", " ")).join("; ")}.</p>}
      <p><strong>Date:</strong> {ad.date_basis === "release_date" ? "Official release" : ad.date_basis}.
        {ad.delivery_start && <> {ad.date_basis === "scheduled_delivery" ?
          "Scheduled interval (not verified delivery days)" : "Reported parent-creative interval"}: {
          displayDate(ad.delivery_start)} – {ad.delivery_end ? displayDate(ad.delivery_end) : "unknown"}.</>}
        Election phase: {ad.phase}. <code>{ad.id}</code></p>
      <p><strong>Matching phrases:</strong> {[...new Set(ad.issues.map(match => match.text))].join(", ") || "None in codebook"}</p>
    </div>}
    <a className="source-link" href={ad.source_url} target="_blank" rel="noopener noreferrer">
      {ad.delivery_start ? "View original creative" : "Read original release"} <span aria-hidden="true">↗</span></a>
  </article>;
}

function Dashboard({ dataset }: { dataset: Dataset }) {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [selected, setSelected] = useState("");
  const [limit, setLimit] = useState(12);
  const ads = useMemo(() => filterAds(dataset.ads, filters), [dataset.ads, filters]);
  const unique = uniqueMessages(ads);
  const ids = new Set(ads.map(ad => ad.id));
  const examples = dataset.examples.filter(example => ids.has(example.ad_id));
  const change = (key: keyof Filters, value: string) => {
    setFilters(previous => ({ ...previous, [key]: value }));
    setLimit(12); setSelected("");
  };
  const reveal = (id: string) => {
    const index = [...ads].sort((a, b) => b.published.localeCompare(a.published)).findIndex(ad => ad.id === id);
    setLimit(Math.max(limit, index + 1)); setSelected(id);
    setTimeout(() => document.getElementById(`ad-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 60);
  };
  const options = (key: "source" | "race" | "sponsor_type") =>
    [...new Set(dataset.ads.map(ad => ad[key]))].sort().map(value =>
      [value, value === "outside_group" ? "Outside group" : value] as [string, string]);
  const filtered = JSON.stringify(filters) !== JSON.stringify(EMPTY_FILTERS);
  const sortedAds = [...ads].sort((a, b) => b.published.localeCompare(a.published) || a.id.localeCompare(b.id));
  return <>
    <a className="skip" href="#main">Skip to analysis</a>
    <header className="masthead"><a href="https://www.themarginoferror.com/">The Margin of Error<span>Data, in context.</span></a>
      <nav aria-label="Page sections"><a href="#analysis">Analysis</a><a href="#evidence">The ads</a><a href="#methods">Methods</a></nav></header>
    <main id="main">
      <section className="hero">
        <p className="eyebrow">THE 2026 MIDTERMS / POLITICAL LANGUAGE</p>
        <h1>The words<br />between the parties.</h1>
        <p className="dek">What Democrats and Republicans say in their ads—and how they describe
          the other side. Read the patterns. Then read the evidence.</p>
        <div className="edition"><span>Federal elections · English-language ads</span>
          <span>Latest release {displayDate(dataset.latest_release)}</span>
          <a href={`${import.meta.env.BASE_URL}report.html`}>Read the report</a></div>
      </section>
      <section className="scope-bar" aria-label="Corpus summary">
        <div><strong>{dataset.ads.length}</strong><span>ad transcripts</span></div>
        <div><strong>{uniqueMessages(dataset.ads).length}</strong><span>unique messages</span></div>
        <div><strong>{new Set(dataset.ads.map(publisher)).size}</strong><span>source publishers</span></div>
        <p>A growing collection of official ad releases, not every ad aired.
          Source and race coverage differ between parties. <a href="#methods">About this collection</a></p>
      </section>
      <section className="filters-panel" aria-labelledby="filter-heading">
        <div className="section-top"><h2 id="filter-heading">Choose your comparison</h2>
          <button className="text-button" onClick={() => { setFilters(EMPTY_FILTERS); setLimit(12); setSelected(""); }}>Reset filters</button></div>
        <div className="filter-grid">
          <Select label="Parties" value={filters.party} options={[["D", "Democratic"], ["R", "Republican"],
            ["other", "Other alignment"], ["unknown", "Unresolved alignment"]]} onChange={value => change("party", value)} />
          <Select label="Chambers" value={filters.chamber} options={[["House", "House"], ["Senate", "Senate"]]} onChange={value => change("chamber", value)} />
          <Select label="States" value={filters.state} options={
            [...new Set(dataset.ads.map(ad => ad.state).filter(Boolean))].sort().map(state => [state, state])
          } onChange={value => change("state", value)} />
          <Select label="Races" value={filters.race} options={options("race")} onChange={value => change("race", value)} />
          <Select label="Publishers" value={filters.source} options={options("source")} onChange={value => change("source", value)} />
          <Select label="Sponsor types" value={filters.sponsorType} options={options("sponsor_type")} onChange={value => change("sponsorType", value)} />
          <Select label="Election phases" value={filters.phase} options={[["general", "General"], ["primary", "Primary"], ["unknown", "Not established"]]} onChange={value => change("phase", value)} />
          <label className="select-label">Released from<input type="date" min="2026-01-01" max={dataset.until}
            value={filters.start} onChange={event => change("start", event.target.value)} /></label>
          <label className="select-label">Released through<input type="date" min="2026-01-01" max={dataset.until}
            value={filters.end} onChange={event => change("end", event.target.value)} /></label>
        </div>
        <div className="search-row"><label htmlFor="search">Search the ad text</label>
          <input id="search" type="search" value={filters.query} placeholder="Try healthcare, border, corruption…"
            onChange={event => change("query", event.target.value)} />
          {filters.issue && <button className="active-filter" onClick={() => change("issue", "")}>
            {filters.issue} ×</button>}</div>
        <p className="result-summary" role="status">{ads.length} records · {unique.length} unique messages
          {filtered ? " in this selection" : " in the collection"}</p>
      </section>
      <section className="section" id="analysis">
        <div className="section-heading"><p className="eyebrow">01 / THE OTHER SIDE</p>
          <h2>How they describe their opponents.</h2>
          <p>Context-checked examples, not a ranking of how often either party attacks.
            Each passage links to its complete ad.</p></div>
        <div className="portrayal-columns">{(["D", "R"] as const).map(party =>
          <div className={`portrayal-column ${party}`} key={party}>
            <h3>{party === "D" ? "Democrats on Republicans" : "Republicans on Democrats"}</h3>
            {examples.filter(example => example.party === party).length === 0 &&
              <p className="empty-inline">No reviewed opponent examples in this selection.</p>}
            {examples.filter(example => example.party === party).map(example =>
              <article className="quote-card" key={example.ad_id + example.quote}>
                <p className="quote-tag">{example.frame} <span>on {example.target}</span></p>
                <blockquote>{example.quote.replace(/^\[NARRATOR\]\s*/, "")}</blockquote>
                <p className="quote-context">{example.context}</p>
                <button className="text-button" onClick={() => reveal(example.ad_id)}>Read the ad in context</button>
              </article>)}
          </div>)}</div>
      </section>
      <section className="section" id="issues">
        <div className="section-heading"><p className="eyebrow">02 / COMMON GROUND, DIFFERENT WORDS</p>
          <h2>What issues appear in the language?</h2>
          <p>Exact matches to published phrase families. This measures wording—not the truth,
            tone, or intent of an ad. Select an issue to explore its evidence.</p></div>
        <BarComparison ads={ads} labels={Object.keys(dataset.codebook.issues)} field="issues"
          onSelect={label => change("issue", label)} />
      </section>
      <section className="section two-panel">
        <div><div className="section-heading"><p className="eyebrow">03 / THE RHETORICAL REGISTER</p>
          <h2>The vocabulary of contrast.</h2><p>Language markers across complete transcripts.
            Quoted or rebutted language is included; these are not confirmed attacks.</p></div>
          <BarComparison ads={ads} labels={Object.keys(dataset.codebook.portrayal_language)}
            field="portrayal_markers" /></div>
        <div><div className="section-heading"><p className="eyebrow">04 / THE CAMPAIGN UNFOLDS</p>
          <h2>New messages over time.</h2><p>First observed release month for each exact unique
            message in the selection. Not spending, impressions, or airing volume.</p></div>
          <div className="legend"><span className="D">Democratic</span><span className="R">Republican</span></div>
          <Timeline ads={ads} />
          <div className="small-note"><strong>Read across like-for-like sources.</strong>
            <p>Publisher choice and race coverage can drive differences. Use chamber, race, and
              publisher filters before interpreting a party-level gap.</p>
            <button className="text-button" onClick={() => change("chamber", "Senate")}>Compare Senate ads</button></div>
        </div>
      </section>
      <section className="section" id="evidence">
        <div className="section-heading"><p className="eyebrow">05 / READ IT FOR YOURSELF</p>
          <h2>The ad library.</h2><p>The complete text, original source, and evidence behind the comparisons.
            Publisher alignment is not necessarily the identity of a creative’s sole payer.</p></div>
        <div className="library-toolbar"><span>{ads.length} matching ad records</span>
          <div><button onClick={() => saveFile("political-ads-selection.csv", csv(ads), "text/csv;charset=utf-8")}>Download CSV</button>
            <button onClick={() => saveFile("political-ads-selection.json", JSON.stringify({
              snapshot_id: dataset.snapshot_id, filters, ads, examples,
              methodology: dataset.methodology,
            }, null, 2), "application/json")}>Download JSON</button></div></div>
        {ads.length === 0 ? <p className="empty-state">No ads match these filters.
          Try a broader date range or reset the selection.</p> :
          <div className="ad-grid">{sortedAds.slice(0, limit).map(ad =>
            <AdCard key={`${ad.id}-${ad.id === selected}`} ad={ad}
              selected={ad.id === selected} examples={dataset.examples} />)}</div>}
        {ads.length > limit && <button className="load-more" onClick={() => setLimit(limit + 12)}>
          Show more ads ({ads.length - limit} remaining)</button>}
      </section>
      <section className="section methods" id="methods">
        <div className="section-heading"><p className="eyebrow">METHODOLOGY & REPRODUCIBILITY</p>
          <h2>What this can—and cannot—tell us.</h2></div>
        <div className="method-grid"><div>
          {dataset.methodology.map((method, index) => <p key={method}><span className="method-number">{String(index + 1).padStart(2, "0")}</span>{method}</p>)}
        </div><div className="method-sidebar">
          <h3>Source coverage</h3>
          <p>Text comes from official releases, public captions, image OCR, native Google previews
            and Snap creatives. Wider Meta, candidate and outside-group coverage remains a goal,
            not an accomplished census. Snap dates are scheduled, not verified daily delivery.</p>
          <table><caption>Current acquisition status</caption><thead><tr><th>Source</th><th>Text records</th><th>Checked</th></tr></thead>
            <tbody>{dataset.sources.map(source => <tr key={source.source}>
              <th><a href={source.url} target="_blank" rel="noopener noreferrer">{source.source.toUpperCase()}</a></th>
              <td>{source.ads_with_text > 0 ? `${source.ads_with_text}${source.state === "partial" ? " (partial)" : ""}` :
                source.state === "ok" ? "0 extracted" : "Not in snapshot"}</td>
              <td>{source.last_success || "—"}</td></tr>)}</tbody></table>
          <p className="fine-print">Record counts before English-language exclusions.
            Failed sources are not counted as zero ad activity. Updates retain last-good text.</p>
          <h3>Review status</h3><p>{dataset.validation.reviewed_examples} source-checked editorial examples.
            No independent human gold set or validated semantic attack classifier is claimed.
            Issue and vocabulary counts are reproducible lexical measures.</p>
          <details><summary>Inspect the phrase codebook</summary><pre>{JSON.stringify(dataset.codebook, null, 2)}</pre></details>
          <h3>Take the evidence with you</h3><p><a href={`${import.meta.env.BASE_URL}data/dataset.json.gz`}>Complete snapshot (compressed JSON)</a></p>
          <p><a href={`${import.meta.env.BASE_URL}data/ads.csv`}>All transcripts and evidence (CSV)</a></p>
          <p><a href="https://github.com/hanshanley/political-ads">Source code and collection methods</a></p>
          <p className="fine-print">Snapshot <code>{dataset.snapshot_id.slice(0, 12)}</code>.
            Collection window: January 1–November 3, 2026. No paid data or model API is required.</p>
        </div></div>
      </section>
    </main>
    <footer><a href="https://www.themarginoferror.com/">The Margin of Error</a>
      <p>Patterns are a starting point. The evidence is the point.</p><span>2026 / POLITICAL ADS</span></footer>
  </>;
}

function App() {
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${import.meta.env.BASE_URL}data/dataset.json`, { signal: controller.signal })
      .then(response => {
        if (!response.ok) throw new Error("Snapshot unavailable");
        return response.json() as Promise<Dataset>;
      })
      .then(setDataset)
      .catch(error => { if (error.name !== "AbortError") setError(true); });
    return () => controller.abort();
  }, []);
  if (error) return <main className="loading"><h1>The evidence could not be loaded.</h1>
    <p>Please reload, or <a href={`${import.meta.env.BASE_URL}report.html`}>read the static report</a>.</p></main>;
  if (!dataset) return <main className="loading" role="status">Loading the ad collection…</main>;
  return <Dashboard dataset={dataset} />;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
