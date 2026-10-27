# Methodology

## What is counted

The target is nationwide federal House/Senate advertising during 2026 through November 3.
The acquisition frame combines official campaign/party/outside-group **ad releases**, native
Google previews and original Snap creatives, not a delivery census. Release, observation,
reported delivery and scheduled-delivery dates are different fields.
A release or YouTube upload does not prove that a creative aired. After-election releases
without independent in-window delivery evidence are excluded.

Analysis includes English text with seeded language-detection probability of at least 0.90,
or local multilingual Whisper English detection at the same threshold for speech-bearing Snap videos.
Hash-bound contextual language adjudications may correct clear detector errors for recovered
English text. They preserve the original automatic label and do not certify extraction accuracy.
Non-English and uncertain text remains in collection inputs but not comparative totals.
This is dominant-language detection, not certification that every word is English: bilingual
passages remain untranslated when a record passes the English threshold.
Source status counts precede this exclusion. Empty results and inaccessible sources differ;
neither establishes that an advertiser ran no ads.

## Attribution and race

Publisher alignment comes from official identity, not ad vocabulary. Publisher, sole creative
payer, and formal party registration are not interchangeable. Coordinated candidate/party
releases need separate payer review before spend attribution. Outside groups receive electoral
alignment, not fabricated formal party registrations.
Unknown and other alignments remain in the explorer and complete exports but do not enter
either Democratic- or Republican-aligned comparison denominator. Parent unions, political
funds and similarly named advocacy organizations are not interchangeable. Optional exact
landing-host constraints reject missing, unrelated and suffix-lookalike hosts.

The FEC candidate master includes primary candidates and federal race metadata. Full first/last
names are conservative matching leads; a surname alone is insufficient. Race inference prioritizes
names in the individual creative, using the release title only if the script has no full-name match.
All names used for inference must map to one race; otherwise it stays unresolved. A title naming
multiple House districts does not assign the first district to every creative. Unambiguous explicit
House district markers and source-specific race assignments are retained. The public roster omits
mailing addresses.

Primary/general phase requires explicit release evidence, not a calendar-date assumption.

## Extraction

Written transcripts begin at explicit markers in identifiable ad releases. Source-specific
boundaries remove press reaction, background, and next-creative titles. Speeches, interview
highlights, phone-menu transcripts, and surrounding commentary are not counted as ad copy.
Duration headings such as `Transcript (30)` and `AD TRANSCRIPT (15s)` delimit separate versions.
Standalone `SCRIPT` headings and explicit "The full text of the ad is below" introductions also
identify publisher scripts. Barr's labeled-speaker paragraphs stop before unlabeled release
background; NRCC targeting lists following scripts are not spoken ad text. Interview/debate
scripts remain excluded.
Horizontal rules terminate scripts before next-ad commentary. Marshall's explicitly marked
transcript paragraphs exclude subsequent release attacks, even when the latter sound like
ad language. Young Kim's April release explicitly describes a primary ad buy; those records
are marked primary rather than used as evidence of cross-party attacks.

Candidate-specific adapters also recover explicitly separated ad scripts and publisher-quoted
ad copy. These records use `publisher_ad_copy` segments and
`publisher_ad_copy_completeness_unverified` flags rather than claiming a complete transcript.
Quoted-copy boundaries exclude spokesperson reactions, biography sections, and background.
Lawler's publisher-quoted dialogue requires explicit ad-specific attribution. Salazar's
quoted-copy boundaries stay within paragraphs and exclude ordinary press-statement attribution.
When a visible Salazar release date disagrees with its CMS date, the CMS date remains the
publication field and both dates plus a discrepancy flag remain in the evidence.

UA Vote! PAC's custom `news` API exposes scripts in its public ACF body rather than a standard
content field. VoteVets's post API exposes no body; its public release's exact article-body
container supplies the script instead. Both sources require an actual 2026 federal candidate
in the script or release heading; unrelated press commentary cannot establish scope.
State-only scripts and video-only pages without written ad text remain excluded. Bipartisan
UA Vote! PAC scripts retain unknown publisher alignment, including support for a Republican.
VoteVets's documented Democratic organizational alignment is not a sole-payer claim for either
its PAC or Action Fund.

Letlow's public blog uses its original `BlogPosting` publication metadata, not sitemap or
modification timestamps, and an exact article-body selector that excludes recent-post cards.
Grothman's campaign-issued release is explicitly identified as reproduced by WisPolitics;
Republican alignment describes the campaign, not the hosting publication. This reviewed
single-release source is marked partial rather than implying exhaustive mirror coverage.

Public uploader captions are preferred to automatic captions. Each cue retains start/end times
and extraction method. Automatic captions are **not independently corrected**: misspelled names,
missing words, music markers, and ambiguous speakers may remain. Original downloaded text is
preserved rather than quietly repaired. A duration/end-coverage check rejects obviously incomplete
tracks but does not certify accuracy. Caption-only records do not yet include on-screen-only
claims; quality flags disclose this without broken-media placeholders.

Public HTML archives backfill HMP and House Majority Forward releases beyond recent-post APIs.
Dated campaign news cards support public HTML acquisition without requiring authenticated APIs;
article titles are checked to reject homepage fallbacks. Squarespace news/media collections follow
explicit pagination offsets and use publisher timezones. NRCC written transcripts
come from its public full-text RSS, not its unauthorized REST endpoint. Partial discovery merges
new evidence without deleting older records. Saved captions retain their original evidence hashes
when rediscovered in an archive; acquisition processes requested sources in priority order and
stops across sources on a caption-service rate limit.

NRCC static graphics are included only after standalone-ad eligibility review, excluding video
thumbnails. Local Apple Vision OCR retains image hashes, line bounds and recognition confidence;
eligibility review does not certify every recognized word. Google native IMAGE/TEXT previews
use the same OCR. Each alternative remains separate rather than inventing a dynamic combination.
Preview-level delivery is not independently verified from Google's parent-creative interval.
Animations and video posters are not silently treated as complete static ads.

Snap's official yearly archive supplies payer names, creative-viewer links, positive impressions,
and scheduled start/stop dates. Exact reported FEC IDs, exact FEC legal-name joins and explicitly
reviewed payer aliases establish federal eligibility; ambiguous/conflicting identities are excluded.
Reviewed advocacy organizations without a registered campaign committee are a separate route: exact payer identity
and organizational alignment require public evidence. Each recovered creative must contain
a full name from the 2026 House/Senate candidate roster or receive an explicit federal-identity
review bound to its exact extraction hash. Evidenced FEC noncommittee disclosure IDs
are retained separately, not called principal-committee IDs. No FEC ID is invented. Inventory leads
awaiting that content check are not yet federal-scope text records.
Twenty-eight explicitly reviewed campaign/ballot-name aliases are bound to actual FEC candidate IDs
in `data/snap-candidate-aliases.json`; they do not overwrite the FEC roster or recognized text.
The same reviewed aliases support federal identity checks for the two new written archives.
For scope qualification only, name matching may span adjacent OCR lines within one frame or
continuous speech cues, never different frames or speech/overlay lanes. The matched context,
frame time, candidate IDs and any reviewed alias evidence are exported. A sole mentioned race
is retained as context, not a validated target assignment. Lexical analysis keeps its stricter
independent-overlay boundaries.
Twenty-seven identity-sensitive creatives have individual reviews in `data/snap-scope-reviews.json`,
with exact recovered quotations, actual FEC candidate IDs, an official evidence URL and rationale.
Examples combine a senator's title with the correct federal office number or explicit federal
policy context. One original video's opening frame explicitly names Ken Paxton where ASR
recognized Paxson; its exact-creative review preserves the recognized text unchanged.
This is not a generic surname or fuzzy-name rule, independent extraction certification or
verification of political claims. Changed inputs, absent quotations and unknown candidate IDs
invalidate a review. Pappas's House/Senate identity ambiguity does not force a single race.
Generic mobilization creatives without federal-candidate evidence remain excluded.
The discovery output retains unmatched public payer/asset identities for further review;
unreviewed or constraint-failing payers are not declared exhausted or automatically federal.
The candidate roster must identify one 2026 federal principal committee. Party/outside-group
identities use a reviewed registry, not political words in the creative. Native images/videos are
accepted only from the actual asset element in Snap's viewer, not site decorations or thumbnails.
Billing addresses and detailed targeting data are not included in the exported lead inventory.

Repeated Snap ad IDs sharing a payer and asset form one creative record, with all eligible
placement IDs and scheduled intervals retained. Positive impressions establish that the platform
reports exposure, not its exact dates or the in-window fraction. Planned start/stop dates and
the union of several placements do not prove continuous delivery, or verified delivery on every
day selected by a date filter. Source/format comparisons separate this evidence from Google
reported delivery and supplementary publisher releases.

Native Snap videos use local multilingual `faster-whisper` base-model speech recognition,
FFmpeg audio decoding, and Apple Vision frames sampled every second plus the end of the video.
Speech cues retain segment timestamps, model revision and extraction diagnostics. If Whisper's
word alignment fails, the local recognizer retries without word timestamps and records the
failure; word probabilities are available only when alignment succeeds. Native frame-decoding
failures may use a local H.264 conversion of the same original, preserving presentation cadence;
both original/derived hashes and the conversion method are retained.
A conservative timing safeguard excludes ASR segments containing at least 20 word tokens at
more than 20 words per reported second. This caught implausible repeated speech, not a
calibrated general ASR-error detector. Rejected speech remains verbatim in exported review
evidence but cannot establish federal scope, suppress genuine OCR as speech duplicates, or
determine an OCR-only record's language. Raw speech caches and evidence source hashes remain
unchanged.
Replaying successfully recovered evidence that now fails scope or review validation withdraws
its stale analyzed record. A network or extraction failure instead preserves prior good text;
raw evidence remains cached in either case.
Frame observations retain actual timestamps, bounds and confidence; an OCR line is an observed
instant, not a verified duration. Original machine text is not quietly corrected. Repeated
on-screen text is counted once; text already present in speech is retained as corroborating
evidence rather than counted again. OCR below 0.80 recognition confidence remains in exported
rejected-observation metadata but outside the analyzed text. That cutoff is not calibrated accuracy.
Transitions, names, small text and short-lived overlays remain extraction risks. Speech and
novel overlays are separate evidence lanes, not a certified sentence or a validated semantic label.
This is partial method/source coverage, not comprehensive local ASR/OCR of every video lead.
No paid recognition or hosted classifier is used. Raw media, caches and model weights remain local.

## Analysis

Exact message identity normalizes only case/whitespace. Changed targets and negation remain
distinct. Source records stay in the explorer; the default denominator is distinct **party +
message** identities after filters. Changed-target templates are not collapsed; they may
still dominate a sample. Caption/transcript mirrors may also remain distinct across methods.

Issue and vocabulary charts match a public, symmetric phrase codebook. Evidence has exact
character offsets, including across caption line breaks. Video speech cues can join in order,
but phrases cannot cross from speech into an overlay or between independent overlay lines;
distinctive n-grams use the same boundaries. A match can be a quotation, rebuttal,
positive self-description, or attack. It is **not a validated semantic label**.
Counts/denominators remain visible; categories overlap. A party with no included messages has
missing comparison evidence, not a zero-percent rate.

Time charts use the first release, reported Google delivery or scheduled Snap start
**within the filtered corpus**, not airings, verified launches or ad duration. Pre-2026
carryovers anchor to January's first in-scope observation rather than a new launch.
Normalized distinctive bigrams/trigrams in JSON require support in three messages.
Smoothed log-odds reflect corpus wording and composition, not causal party preferences.
The dated source-coverage table in `SOURCES.md` distinguishes monthly unique messages from
the number of publishers represented. Repeated identical scripts across district releases count
once; templates changing a candidate name remain distinct. A burst from one committee is not
independent evidence from many campaigns, and sparse early months cannot support national trends.

`python -m political_ads.cli analyze` generates a **local-only** research report in
`outputs/analysis.html`, complete evidence/text in `outputs/analysis.json`, and all analyzed
records in `outputs/analysis-ads.csv`. It does not build, publish, or deploy the website.
Comparisons cover month, chamber, sponsor type, publisher, race, election phase, placement and
record format. Monthly lexical denominators use first-observed exact messages across the saved
corpus; non-temporal strata deduplicate after filtering. Coverage distinguishes all records, first messages,
and publishers. Publisher counts and sensitivity checks group matching sponsor names across
source/platform IDs; they do not infer mergers between different sponsor names.
Included record/message IDs make each numerator and denominator inspectable.
A sensitivity table removes each alignment's largest publisher by record count and recomputes
message denominators. This is a composition diagnostic, not reweighting or a representative
party comparison. Full text, original evidence, and extraction flags remain in the JSON/CSV.

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
