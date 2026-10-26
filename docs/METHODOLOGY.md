# Methodology

## What is counted

The target is nationwide federal House/Senate advertising during 2026 through November 3.
The current acquisition frame is official campaign, party, and aligned outside-group **ad releases**,
not a delivery census. Release, observation, and delivery dates are different fields.
A release or YouTube upload does not prove that a creative aired. After-election releases
without independent in-window delivery evidence are excluded.

Analysis includes English text with seeded language-detection probability of at least 0.90.
Non-English and uncertain text remains in collection inputs but not comparative totals.
Source status counts precede this exclusion. Empty results and inaccessible sources differ;
neither establishes that an advertiser ran no ads.

## Attribution and race

Publisher alignment comes from official identity, not ad vocabulary. Publisher, sole creative
payer, and formal party registration are not interchangeable. Coordinated candidate/party
releases need separate payer review before spend attribution. Outside groups receive electoral
alignment, not fabricated formal party registrations.

The FEC candidate master includes primary candidates and federal race metadata. Full first/last
names are conservative matching leads; a surname alone is insufficient. A race is inferred only
when every matched candidate maps to that race; otherwise it stays unresolved. Explicit House
district markers and source-specific race assignments are retained. The public roster omits
mailing addresses.

Primary/general phase requires explicit release evidence, not a calendar-date assumption.

## Extraction

Written transcripts begin at explicit markers in identifiable ad releases. Source-specific
boundaries remove press reaction, background, and next-creative titles. Speeches, interview
highlights, and surrounding commentary are not counted as ad copy.

Candidate-specific adapters also recover explicitly separated ad scripts and publisher-quoted
ad copy. These records use `publisher_ad_copy` segments and
`publisher_ad_copy_completeness_unverified` flags rather than claiming a complete transcript.
Quoted-copy boundaries exclude spokesperson reactions, biography sections, and background.

Public uploader captions are preferred to automatic captions. Each cue retains start/end times
and extraction method. Automatic captions are **not independently corrected**: misspelled names,
missing words, music markers, and ambiguous speakers may remain. Original downloaded text is
preserved rather than quietly repaired. A duration/end-coverage check rejects obviously incomplete
tracks but does not certify accuracy. Caption-only records do not yet include on-screen-only
claims; quality flags disclose this without broken-media placeholders.

Public HTML archives backfill HMP releases beyond the recent-post API. NRCC written transcripts
come from its public full-text RSS, not its unauthorized REST endpoint. Partial discovery merges
new evidence without deleting older records. Saved captions retain their original evidence hashes
when rediscovered in an archive; acquisition processes requested sources in priority order and
stops across sources on a caption-service rate limit.

The publication does not claim completed local ASR/OCR coverage. No paid recognition or hosted
classifier is used. Raw media, caches, and optional model files remain local-only.

## Analysis

Exact message identity normalizes only case/whitespace. Changed targets and negation remain
distinct. Source records stay in the explorer; the default denominator is distinct **party +
message** identities after filters. Changed-target templates are not collapsed; they may
still dominate a sample. Caption/transcript mirrors may also remain distinct across methods.

Issue and vocabulary charts match a public, symmetric phrase codebook. Evidence has exact
character offsets, including across caption line breaks. A match can be a quotation, rebuttal,
positive self-description, or attack. It is **not a validated semantic label**.
Counts/denominators remain visible; categories overlap. A party with no included messages has
missing comparison evidence, not a zero-percent rate.

Time charts count first release of each message **within the filtered corpus**, not airings or
ad duration. Normalized distinctive bigrams/trigrams in JSON require support in three messages.
Smoothed log-odds reflect corpus wording and composition, not causal party preferences.

Opponent passages are individually read editorial examples bound to source hashes and exact
quotations. They illustrate framing, not random sampling, independent human gold, or national
prevalence. Speaker identity remains uncertain unless established by the source. Changed evidence
stops publication pending review.

There is **no representative held-out semantic evaluation**. Semantic attack/support rates,
semantic issue classifications, and model accuracy claims are therefore withheld.

## Interpretation

Source, race, sponsor, date, and extraction mixes differ by party. The first release pilot
particularly overrepresented Democratic House and Republican Senate material. Added outside
groups broaden coverage without eliminating bias. Use race/chamber/source filters and read
individual ads; even within-Senate comparisons are not automatically like-for-like.

The project does not verify claims, infer intent/voter beliefs, estimate persuasion, or turn
incompatible impression/spending ranges into precise exposure. Complete selected-record CSV/JSON
uses the charts' filter scope. Spreadsheet-sensitive cells receive an apostrophe prefix;
JSON retains exact original text.
