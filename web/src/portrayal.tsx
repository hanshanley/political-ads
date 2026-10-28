import { useMemo, useState } from "react";
import {
  type Ad, type Dataset, type PortrayalScope, type ToneCategory, partyName,
  adStrategyLabels, adStrategySummary, portrayalSummary, selectPortrayalEvidence,
} from "./data";

const toneLabels: Record<ToneCategory, string> = {
  "negative-only": "Negative only",
  "positive-only": "Positive only",
  mixed: "Mixed",
  "neutral-only": "Neutral only",
};

const percent = (count: number, total: number) => total ? `${(count / total * 100).toFixed(1)}%` : "—";
const frameLabel = (frame: string) => frame.replaceAll("_", " ")
  .replace(/\b\w/g, letter => letter.toUpperCase());

export function PortrayalAnalysis({ ads, codebook, reveal }: {
  ads: Ad[]; codebook?: Dataset["portrayal_codebook"]; reveal: (id: string) => void;
}) {
  const [scope, setScope] = useState<PortrayalScope>("opponents");
  const summary = useMemo(() => portrayalSummary(ads, scope), [ads, scope]);
  const strategies = useMemo(() => adStrategySummary(ads), [ads]);
  const frames = [...new Set((["D", "R"] as const).flatMap(party =>
    Object.keys(summary[party].frames)))]
    .sort((a, b) => (summary.D.frames[b] ?? 0) + (summary.R.frames[b] ?? 0) -
      (summary.D.frames[a] ?? 0) - (summary.R.frames[a] ?? 0) || a.localeCompare(b));
  const direction = (party: "D" | "R") => scope === "opponents" ?
    party === "D" ? "Democrats on Republican people" : "Republicans on Democratic people" :
    party === "D" ? "Democrats on their supported candidates" : "Republicans on their supported candidates";

  return <section className="section portrayal-analysis" id="analysis">
    <div className="section-heading portrayal-heading">
      <p className="eyebrow">01 / PORTRAYALS OF PEOPLE</p>
      <h2>How the parties describe political people.</h2>
      <p>Target-attributed descriptions in exact, deduplicated messages—not words merely near a name.
        Tone describes the portrayal of the target, not the ad’s emotion or whether a claim is true.</p>
    </div>
    <aside className="review-coverage" aria-labelledby="coverage-heading">
      <div><p className="eyebrow">REVIEW COVERAGE</p><h3 id="coverage-heading">What has actually been reviewed</h3>
        <p>AI-assisted labels are source-bound editorial annotations, not an independent human gold set.
          Missing and stale reviews do not enter portrayal metrics.</p></div>
      <div className="coverage-parties">{(["D", "R"] as const).map(party => {
        const item = summary[party];
        return <div key={party}>
          <strong className={party}>{partyName(party)}</strong>
          <dl><div><dt>Reviewed</dt><dd>{item.coverage.reviewed}/{item.messages || "—"}</dd></div>
            <div><dt>Uncertain</dt><dd>{item.coverage.uncertain}</dd></div>
            <div><dt>Unreviewed</dt><dd>{item.coverage.unreviewed}</dd></div>
            <div><dt>Stale</dt><dd>{item.coverage.stale}</dd></div></dl>
        </div>;
      })}</div>
    </aside>

    <div className="frame-section ad-strategy">
      <div className="section-heading"><p className="eyebrow">THE WHOLE AD</p>
        <h3>Praise, attacks, or both in the same ad?</h3>
        <p>Own-side praise means an endorsed positive description of a supported person or party
          collective with the advertiser’s party. Opponent criticism means an endorsed negative
          description of the opposing party’s people or collectives. Mixed/contrast requires both
          in the same message.</p></div>
      <div className="frame-table" role="table" aria-label="Same-ad praise and attack">
        <div className="frame-row frame-header" role="row">
          <span role="columnheader">Ad-level category</span>
          <span role="columnheader" className="D">Democratic</span>
          <span role="columnheader" className="R">Republican</span>
        </div>
        {Object.entries(adStrategyLabels).map(([key, label]) => {
          const category = key as keyof typeof adStrategyLabels;
          return <div className="frame-row ad-strategy-row" role="row" key={key}>
            <span role="rowheader">{label}</span>
            {(["D", "R"] as const).map(party => {
              const { messages, counts } = strategies[party];
              return <div role="cell" key={party} className={party}>
                <div className="tone-track"><i style={{ width: `${
                  messages ? counts[category] / messages * 100 : 0}%` }} /></div>
                <b>{percent(counts[category], messages)}</b>
                <small>{messages ? `${counts[category]}/${messages}` : "—"}</small>
              </div>;
            })}
          </div>;
        })}
      </div>
      <p className="chart-caption">Denominator: all unique messages of each advertiser alignment,
        including ads without a person description. These five categories are mutually exclusive.
        “Only” refers to the two signals above; other sentiments can coexist. Neither does not mean
        neutral. Uncertain, unreviewed and stale messages remain separate. Quoted opponents,
        rebutted/unclear voices, same-party rival attacks and unknown target parties do not supply
        either signal. Displayed percentages are rounded. This is different from mixed tone
        within one target scope below.</p>
    </div>

    <div className="portrayal-switch" role="group" aria-label="People being described">
      {([["opponents", "Opponents"], ["self", "Their own candidates"]] as const).map(([value, label]) =>
        <button key={value} aria-pressed={scope === value}
          onClick={() => setScope(value)}>{label}</button>)}
    </div>

    <div className="tone-columns">{(["D", "R"] as const).map(party => {
      const item = summary[party];
      return <article className="tone-column" key={party}>
        <header><p className={`party-kicker ${party}`}>{direction(party)}</p>
          <strong>{item.eligible}/{item.coverage.reviewed} reviewed messages had an eligible
            person description</strong>
          <span>{item.coverage.reviewed - item.eligible} reviewed messages had no eligible
            description in this scope.</span></header>
        <div className="tone-overlap" aria-label={`${partyName(party)} negative and positive shares`}>
          <div><span>Any negative</span><b>{percent(item.negative, item.eligible)}</b>
            <small>{item.eligible ? `${item.negative}/${item.eligible}` : "no evidence"}</small></div>
          <div><span>Any positive</span><b>{percent(item.positive, item.eligible)}</b>
            <small>{item.eligible ? `${item.positive}/${item.eligible}` : "no evidence"}</small></div>
        </div>
        <div className="tone-breakdown">{(Object.keys(toneLabels) as ToneCategory[]).map(tone =>
          <div key={tone}><span>{toneLabels[tone]}</span>
            <div className="tone-track"><i className={`${party}`}
              style={{ width: `${item.eligible ? item.tones[tone] / item.eligible * 100 : 0}%` }} /></div>
            <b>{percent(item.tones[tone], item.eligible)}</b>
            <small>{item.eligible ? `${item.tones[tone]}/${item.eligible}` : "—"}</small>
          </div>)}</div>
      </article>;
    })}</div>
    <p className="chart-caption portrayal-caption">Negative only, positive only, mixed and neutral only
      are mutually exclusive. “Any negative” and “any positive” both include mixed messages, so they overlap.
      Mixed can include descriptions of different people within the selected scope.
      The denominator is messages with at least one eligible person description; a message without one is
      not neutral. Quoted-opponent, rebutted-claim and unclear voices are excluded, while advertiser speech
      and clips the ad adopts are included.</p>

    <div className="frame-section">
      <div className="section-heading"><p className="eyebrow">FRAME CONTRASTS</p>
        <h3>What kind of portrayal is it?</h3>
        <p>Each exact message counts once per frame and party. Frames can overlap; every percentage uses
          the same eligible-description denominator as the tone comparison.</p></div>
      {!frames.length ? <p className="empty-inline">No reviewed person-level frames in this selection.</p> :
        <div className="frame-table" role="table" aria-label="Portrayal frames">
          <div className="frame-row frame-header" role="row">
            <span role="columnheader">Portrayal frame</span>
            <span role="columnheader" className="D">Democratic</span>
            <span role="columnheader" className="R">Republican</span>
          </div>
          {frames.map(frame => <div className="frame-row" role="row" key={frame}
            title={codebook?.frames?.[frame] ?? frameLabel(frame)}>
            <span role="rowheader">{codebook?.frames?.[frame] ?? frameLabel(frame)}</span>
            {(["D", "R"] as const).map(party => <div role="cell" key={party} className={party}>
              <div className="tone-track"><i style={{ width: `${
                summary[party].eligible ? (summary[party].frames[frame] ?? 0) /
                  summary[party].eligible * 100 : 0}%` }} /></div>
              <b>{percent(summary[party].frames[frame] ?? 0, summary[party].eligible)}</b>
              <small>{summary[party].eligible ?
                `${summary[party].frames[frame] ?? 0}/${summary[party].eligible}` : "—"}</small>
            </div>)}
          </div>)}
        </div>}
    </div>

    <div className="portrayal-evidence">
      <div className="section-heading"><p className="eyebrow">ORIGINAL LANGUAGE</p>
        <h3>Descriptors in their exact attributed passages.</h3>
        <p>Short phrases are shown with the stored supporting quote, target and tone.
          Examples are selected deterministically: common frames first, then distinct messages,
          targets and tone where available—never by phrase severity. Expand a supporting passage
          or open the complete ad for context.</p></div>
      <div className="portrayal-columns">{(["D", "R"] as const).map(party => {
        const evidence = selectPortrayalEvidence(summary[party].evidence);
        return <div className="portrayal-column" key={party}>
          <h4 className={party}>{direction(party)}</h4>
          {!evidence.length && <p className="empty-inline">
            No eligible reviewed phrases in this selection.</p>}
          {evidence.map(({ adId, description }, index) =>
            <article className="quote-card" key={`${adId}-${description.start}-${index}`}>
              <p className="quote-tag"><span className={`tone-pill tone-${description.tone}`}>
                {description.tone}</span> {description.target} · {frameLabel(description.frame)}</p>
              <p className="descriptor-phrase">“{description.phrase}”</p>
              <details className="supporting-passage"><summary>Supporting passage</summary>
                <blockquote>{description.quote}</blockquote>
              </details>
              <button className="text-button" onClick={() => reveal(adId)}>Read the full ad</button>
            </article>)}
        </div>;
      })}</div>
    </div>
  </section>;
}
