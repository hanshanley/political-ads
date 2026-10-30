# Methodology

## Start here: how classification actually works

**The headline portrayal labels are saved AI judgments, not keyword scores and not
independently validated human labels.** GPT-5.6 Sol was used to interpret the recovered
ad text. Python then turns those saved judgments into chart categories using fixed
rules. Running the build repeats the counting, not the AI interpretation.

The project has three different kinds of classification. They answer different questions:

| Classification | Question it answers | How it is assigned |
|---|---|---|
| Publisher alignment | Is this advertiser Democratic-aligned, Republican-aligned, other or unknown? | Publisher/candidate identity and documented electoral-program evidence, including saved alignment reviews; not the sentiment of the ad. |
| Contextual portrayal | Who is being described, what is said about them, and is that description positive, negative or neutral? | Saved AI-assisted reading of the complete recovered text, under a written codebook. |
| Issue/vocabulary match | Does the recovered text contain a listed word or phrase? | Automatic phrase matching against `data/codebook.json`; no contextual judgment. |

Calling all three "classification" without distinguishing them obscures the method.
In particular, an issue-word match is **not** a model's judgment about the ad's main
issue, and a negative word is **not** automatically a negative portrayal of an opponent.

### 1. First, recover the words and identify the advertiser

The input is a collection of recovered ad texts: publisher scripts, captions, and
locally recognized speech or on-screen text. It is not a representative sample of
everything voters saw. A script's release does not prove that the ad aired, and
machine transcription can miss or misrecognize words.

Only eligible English, in-window records enter the comparisons. The collection's final
date limit is November 4, 2026; that is not a claim that observations already extend
to that date. Democratic and Republican comparisons use advertiser alignment, not an
assumption that every person mentioned shares or opposes that alignment. Other and
unknown advertisers remain in the exports but outside those two comparison groups.

### 2. Next, the AI review assigns descriptions, not one sentiment to the whole ad

The saved review process identifies **GPT-5.6 Sol** as the AI-assisted reviewer.
The codebook instructs it to read the entire recovered message, including negation
and quotations, rather than retrieve snippets containing negative words.
The resulting review is stored in `data/portrayal-reviews.json`.

A message can contain no descriptions, one description, or several. Each description
records these separate judgments:

| Field | What the reviewer must decide |
|---|---|
| Target and kind | Who is being described? Is it an individual person or a collective such as a party? |
| Target party and role | What is that target's party, and is the target supported by the advertiser, an opponent, or unclear? Party must have an identity basis, not be inferred from hostility. |
| Tone | Does this particular passage describe the target positively, negatively or neutrally? This is not the emotional mood of the whole ad. |
| Frame | What kind of description is it: competence, integrity, interests, ideology, connection, leadership, independence, record, safety/rights, background or other? |
| Voice | Is this the advertiser's own claim, an adopted clip, a quoted opponent, a rebutted accusation, or unclear? Only the first two count in the headline comparisons. |
| Evidence | Which literal phrase and supporting passage express the description, and which words identify the target? Character positions link them to the saved text. |

For example, saying that prices are high is not by itself a description of a candidate.
Attributing a harmful vote to a named candidate can be a negative description of that
candidate's record. A pledge can count as a record/policy-commitment description, but
does not establish that the promised outcome happened. These distinctions require
interpretation; the presence of a word alone cannot settle them.

The review status is also separate from the labels: `reviewed` means a saved decision
is available, `uncertain` means the review did not resolve the message, `unreviewed`
means no applicable decision exists, and `stale` means changed text, sponsor or alignment
prevents reuse. **Reviewed does not mean independently verified or correct.**
A reviewed message with no attributable descriptions is not a neutral description.

### 3. Then, Python derives two different headline measures

Before counting, the code selects one representative of each exact message within
each advertiser alignment. Here "exact" ignores capitalization and whitespace, but
preserves punctuation, names and negation. Identical text within one alignment counts
once even if multiple sponsors publish it. The earliest in-scope observation wins,
with ad ID breaking ties; a later reviewed copy does not replace an unreviewed one.
Filters are applied before this selection.

**Whole-ad strategy asks: does this message praise its own side, criticize the other
party, both, or neither?** It looks at all endorsed descriptions of people and collectives.
Own-side praise requires a positive description of a supported target with the
advertiser's party. Opponent criticism requires a negative description of an opponent
with the other D/R party. Both signals in one message produce mixed/contrast.
Unknown-party targets and same-party rivals cannot supply the cross-party criticism signal.
Messages without usable reviews get a separate uncertain/missing category.

**Person-portrayal tone asks: how does this message describe people in a particular
scope?** The principal opponent scope includes only people identified as opponents
from the other party. Supported people, same-party opponents and opposing collectives
have separate scopes. Within a scope, positive and negative descriptions together
produce mixed tone, even if they concern different people. Neutral facts do not turn
an otherwise positive or negative message into mixed.

These are not interchangeable. An ad praising its candidate and attacking the other
party's candidate is mixed/contrast as a whole, but can be positive-only about supported
people and negative-only about opponents.

### 4. A real saved decision, from text to category

Record `barr-1387-0`, sponsored by Andy Barr for Senate, has Republican advertiser
alignment. Its saved review contains three descriptions:

| Target | Saved interpretation | Contribution to whole-ad strategy |
|---|---|---|
| Andy Barr | Supported Republican person; positive leadership description, evidenced by "leading the fight to end it for good"; advertiser voice. | Supplies own-side praise. |
| "woke liberals" | Opposing collective; negative ideology description; target party unknown. | Does not supply other-party criticism: the review does not identify a D/R party. |
| "corporate losers" | Opposing collective; negative competence description; target party unknown. | Does not supply other-party criticism for the same reason. |

The resulting whole-ad category is **own-side praise only**, even though the text
contains insults. "Only" means that the other defined signal is absent, not that
the entire ad is positive. Its supported-person tone is positive-only. It contributes
no description to the cross-party-opponent-person tone denominator: neither negative
description is of an identified other-party person.

This example explains the saved labels and their consequences; it is not an independent
endorsement of the AI's interpretation or a claim that its description list is exhaustive.
The source record is in `data/site/corpus.json`; the decision is in
`data/portrayal-reviews.json`. Search both for `barr-1387-0`.

### 5. Read each percentage with its own denominator

| Measure | Numerator | Denominator |
|---|---|---|
| Whole-ad strategy, such as mixed/contrast | Unique messages assigned that strategy | **All unique messages** for that advertiser alignment, including uncertain/missing reviews |
| Person-portrayal tone, such as negative-only about opponents | Reviewed unique messages with that tone in the selected scope | **Reviewed unique messages with an endorsed description in that scope** |
| Portrayal frame, such as integrity | Reviewed unique messages with that frame in the selected scope | The same scope-specific description denominator; multiple frames can count for one message |
| Issue/vocabulary match, such as healthcare | Unique messages containing at least one listed phrase in that family | **All unique messages** for that advertiser alignment, whether context-reviewed or not |

For a **hypothetical** group of 100 unique messages, suppose 40 have reviewed
other-party-person descriptions and 30 of those are negative-only. The opponent-tone
chart reports `30 / 40 = 75%`, not `30 / 100`. If 20 of the 100 have both own-side
praise and other-party criticism, the strategy chart reports `20 / 100 = 20%`.
The two percentages answer different questions. Repeated descriptions do not give
a message extra weight, and no measure is weighted by spending or impressions.

### 6. What is automated, and what has not been established?

The phrase charts are fully rule-based: for example, a listed healthcare phrase
can match even inside a denial or quotation. Families overlap, and there is no
single exclusive "main issue" assignment.

The portrayal charts instead depend on the saved AI judgments. The ledger records
an AI-assisted repair pass, but **there is no independent held-out human evaluation,
inter-rater agreement result or measured semantic accuracy**. Hash and quotation checks
can establish that a label points to unchanged text; they cannot establish that the
target, tone or frame was interpreted correctly.

The original exact prompts, backend revision, decoding settings and random seeds
are not retained. The saved codebook documents the intended rules; it is not a
complete record of the original model calls. Therefore the original annotation run
cannot be independently recreated from this repository alone.

`build`, `analyze` and the scheduled refresh do not ask a model to label text.
They reuse applicable saved reviews; new or changed texts remain unreviewed or stale.
The independent strategy auditor checks that the saved labels were counted correctly,
**not that the labels are semantically correct**.

The defensible interpretation is: **these are exploratory patterns in this recovered
collection, conditional on AI-assisted labels and uneven source coverage**. They do
not estimate all national advertising, exposure, persuasion, or the truth of ad claims.

## Technical reference

The sections below retain the exact selection rules, decision table, reproduction
commands and source-specific extraction details. For a count audit, start with
[the exact calculation](#exact-calculation) and
[reproduction instructions](#reproduce-and-inspect-the-decisions).
For the annotation rules, see
[`data/portrayal-codebook.json`](../data/portrayal-codebook.json) and
[context-coded descriptions](#context-coded-descriptions-of-people).

## What is counted

The target is nationwide federal House/Senate advertising during 2026 through November 4,
inclusive. November 4 is the final scope limit, not the current snapshot's observation date;
future dates are never represented as collected. Post-election releases retain their dates
and are not described as pre-election delivery.
The acquisition frame combines official campaign/party/outside-group **ad releases**, native
Google previews and original Snap creatives, not a delivery census. Release, observation,
reported delivery and scheduled-delivery dates are different fields.
A release or YouTube upload does not prove that a creative aired. Releases after November 4
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

## Same-ad praise and criticism

The whole-ad strategy partition uses all exact, deduplicated messages of each advertiser
alignment as the denominator, not only messages with a person description. Endorsed positive
descriptions of supported people/collectives with the advertiser's own party supply the
own-side praise signal. Endorsed negative descriptions of opposing-party people/collectives
supply the opponent-criticism signal. Mixed/contrast requires both in the same message.
Same-party rival attacks, unknown target parties, quoted opponents, rebutted accusations and
unclear voices do not supply either signal. Adopted clips can count.

The mutually exclusive categories are own-side praise without opponent criticism, both signals,
opponent criticism without own-side praise, neither signal, and uncertain/unreviewed/stale.
"Only" refers to these two signals; other sentiments can coexist. Neither is not neutral,
and missing reviews are not assigned to neither. Every category retains counts, the all-message
denominator, shares and exact message IDs. Source sensitivity recomputes the partition after
the largest-publisher exclusions and deduplication. This does not change the separate
person-scope mixed-tone measure, which can combine positive and negative descriptions
of people within one scope.

### Exact calculation

The **semantic input** is the saved, AI-assisted description ledger, not a sentiment-word
count. The AI-assisted review records who is being described in the complete recovered
text, their role/party, whether the advertiser endorses the description, and its tone. A negative
description of a policy or price alone is not automatically an attack on a person.
The **aggregation** below is deterministic and symmetric for D and R:

1. Load the committed text partitions and candidate/alignment metadata; include only
   eligible English, in-window records. Other and unknown advertiser alignments stay
   in the explorer/export but not the D/R comparison.
2. Attach saved reviews only to matching raw text, sponsor and alignment. A changed
   publisher-page hash alone does not invalidate unchanged text; changed text/sponsor/
   alignment makes the old decision stale. Missing reviews are not inferred.
3. After any dashboard filters, normalize whitespace to single spaces, trim and case-fold
   the complete text, then SHA-256 hash it. The deduplication key is `(alignment, message_id)`,
   **not** sponsor, source, creative ID, target, wording similarity or a paid placement.
   Punctuation, changed names and negation are preserved.
4. Sort by in-scope observation date, then locale-independent lexicographic ad ID,
   and keep the first record for each key. The date is
   `max(2026-01-01, delivery_start)` when present; otherwise it
   is `published`. Snap's delivery-start field is a scheduled date, not verified delivery.
   Review status does **not** affect selection: a later reviewed mirror cannot replace an
   earlier unreviewed record. Exact same-party text from different sponsors collapses
   under this rule, but reviews do not transfer across sponsors. This may lose context;
   the audit exposes the selected sponsor and review rather than combining their labels.
5. If that representative is uncertain, unreviewed or stale, assign `not_reviewed`
   before testing any descriptions. Otherwise consider only `advertiser` and `adopted_clip`
   descriptions. A praise signal needs `target_party == alignment`,
   `target_role == self_or_supported`, and `tone == positive`. A criticism signal needs
   the **other D/R party**, `target_role == opponent`, and `tone == negative`.
   Both person and collective targets can supply either signal. One eligible passage
   suffices; repeated passages or frames do not add more than one message.
6. Apply this mutually exclusive decision table, then divide each count by **all**
   selected messages for that advertiser alignment. No spending/impression weight is used.

| Review status | Own praise | Opponent criticism | Category |
|---|---|---|---|
| Reviewed | Yes | No | Own-side praise only |
| Reviewed | Yes | Yes | Mixed/contrast |
| Reviewed | No | Yes | Opponent criticism only |
| Reviewed | No | No | Neither signal |
| Uncertain, unreviewed or stale | Not tested | Not tested | Uncertain or missing review |

For category `c` and alignment `p`, `share = count(c, p) / all_unique_messages(p)`.
Store the unrounded fraction and exact IDs; multiply by 100 and round to one decimal
only for display. All five counts exhaust the denominator; rounded percentages need
not add to exactly 100. A zero denominator yields `null`/an em dash, not 0%.
For the saved October 28 snapshot, Democratic mixed/contrast is `105 / 1200 = 8.75%`,
displayed as **8.8%**; Republican mixed/contrast is `76 / 459 = 16.5577...%`,
displayed as **16.6%**. These are shares of unique recovered messages, not airings.

An ad praising its supported candidate and criticizing an opposing candidate has
same-ad mixed/contrast strategy even when its self scope is positive-only and its
opponent scope negative-only. Conversely, an ad both praising and criticizing an
opponent has within-opponent mixed tone, but does not have same-ad contrast unless
it also praises its own party's supported people/collectives.

The source check removes each alignment's largest publisher by **pre-deduplication
eligible source-record count**, with publisher-name alphabetical order breaking ties.
Publisher is the sponsor name, falling back to the collection-source ID with its
platform suffix removed. Exclude that publisher's records **before deduplicating again**;
do not simply subtract its representative IDs, because another publisher's mirror can
remain. At the saved snapshot this excludes AFL-CIO for D and Senate Leadership Fund
for R, leaving 919 and 309 messages. Praise-only becomes 31.1% D / 37.9% R and
criticism-only 44.8% D / 31.4% R: both raw party orderings reverse. This is a
source-composition diagnostic, not representative adjustment.

### Reproduce and inspect the decisions

After installing the README dependencies, all commands below use the committed
`data/site/*.json` partitions, metadata/codebooks and `data/portrayal-reviews.json`.
They require no raw-media cache, processed Parquet, API credentials, network requests
or model service. Record `git rev-parse HEAD`: daily research refreshes can change
the inputs and results. The October 28 worked example above uses snapshot
`dfdf38b6b26fd7d36924d0fe6c6e653ac68d5d5cc5a0998d304568867d1e35b0`.

```bash
git rev-parse HEAD
.venv/bin/python -m political_ads.cli build
.venv/bin/python -m political_ads.cli validate
.venv/bin/python -m political_ads.cli audit-strategy --output /tmp/political-ads-strategy-audit.json
```

`political_ads/portrayals.py` attaches saved reviews and derives the production
tone/frame/strategy categories; it does not run the AI reviewer.
`political_ads/strategy_audit.py` independently applies the decision table; it does not
call the production classifier, strategy summary or deduplication helper. It first
checks the saved analysis against the canonical inputs, then verifies every full and
source-excluded category's exact IDs/count/total/unrounded share and the chart CSV.
Any discrepancy exits nonzero; the command does not overwrite or repair research outputs.
CI and automatic research refresh run it after build/validation.

The optional audit JSON retains each selected message's complete `text`, sponsor,
source URL, hashes, selection date, assigned `category` and full attached `review`.
`own_praise_description_indices` and `opponent_criticism_description_indices` are
zero-based indices into `review.descriptions`: follow them to the literal passage,
target anchor, character offsets, target party/role, tone and voice that supplied each
signal. Empty lists for a reviewed message mean no eligible signal was coded, not
that a human certified its absence. Missing-review rows preserve their status/reason.
`source_excluded_message_ids` identifies the retained sensitivity representatives.
If exclusion selects a different mirror, `source_excluded_replacement_messages`
retains its complete text, review and signal indices too; no retained sensitivity
record is represented only by metadata.
The printed summary and JSON also record the snapshot ID, input SHA-256 hashes,
saved annotation provenance, Python version and installed package versions.
`outputs/analysis.json` retains **all** analyzed source records, including unselected
mirrors; the audit export is the explicitly deduplicated D/R comparison set.

**Reproducibility boundary:** the ledger identifies GPT-5.6 Sol as the AI-assisted
reviewer and retains the original frozen input snapshot, repair-process metadata
and bound decisions. It does not contain exact original prompts, backend revision,
decoding parameters or random seeds. A build replays these decisions; it does not
recreate them from raw text. Do not claim independent semantic accuracy, inter-rater
agreement or a fully reproducible model-labeling experiment. Re-annotation requires
reading the full text under the codebook and versioning any changed decisions; it
is separate from reproducing the current calculations. PNG bytes may also vary with
Matplotlib/font/platform versions even when all counts and evidence are identical;
record the runtime when comparing images, rather than expecting cross-platform
byte identity.

## Attribution and race

Publisher alignment comes from official identity, not ad vocabulary. Publisher, sole creative
payer, and formal party registration are not interchangeable. Coordinated candidate/party
releases need separate payer review before spend attribution. Outside groups receive electoral
alignment, not fabricated formal party registrations.
Unknown and other alignments remain in the explorer and complete exports but do not enter
either Democratic- or Republican-aligned comparison denominator. Parent unions, political
funds and similarly named advocacy organizations are not interchangeable. Optional exact
landing-host constraints reject missing, unrelated and suffix-lookalike hosts.

Publisher electoral-program reviews are separate from raw identity mappings.
`data/publisher-alignments.json` binds each applied decision to a specific acquired ID,
source, sponsor, original classification and source hash. The derived corpus preserves
`original_alignment` and complete `alignment_review` evidence in JSON/CSV. Changed hashes,
identities or original labels cannot inherit a review: they keep their acquisition alignment
and receive a stale-review quality flag. New records do not inherit decisions automatically.
OCR, speech, candidate-scope and language reviews are not recomputed or rebound for this layer.

Missing FEC party registration is not equivalent to unknown electoral alignment. Editorial
D/R groupings use documented current federal electoral programs: an explicit organizational
program/endorsement record, or the exact filer's reported general-election support/oppose
directions. Primary-only spending cannot by itself establish alignment. Documented parent/program
relationships may substantiate organizational alignment without transferring committee IDs,
merging legal payers or asserting sole creative funding. FEC evidence is qualitative, not a
sum of amended transactions or an expenditure-to-creative attribution.

Democratic-leaning is not synonymous with exclusively Democratic: AFL-CIO's current
endorsement evidence includes Republican and independent candidates, and Lower Costs Now
and CFFE support independents. These exceptions are explicit in the reviews. UA's own current
program and releases establish bipartisan support, retained as other rather than unknown.
Remaining unknowns carry reviewed reasons. Neither labor affiliation, policy positions,
hostile wording nor a suggestive payer name alone establishes alignment. Publisher groupings
do not determine whether an individual ad supports or attacks a particular party.

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
State-only scripts and video-only pages without written ad text remain excluded. UA Vote! PAC's
raw acquisition alignment remains unknown; its hash-bound publisher-program review yields
other/bipartisan in derived exports, including when a particular script supports a Republican.
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

Individually reviewed campaign originals require a direct link from the campaign's public
page, exact original-byte SHA-256, actual 2026 federal-candidate identity and retained approval/
payer evidence. Feed originals also require the exact reviewed post ID and Unix timestamp.
Paginated originals replay only the campaign homepage's exposed same-origin public feed
form, with its exact reviewed fields and public button/feed binding. Evidence retains
both the homepage and actual paginated-response hashes; original links must still match
the reviewed post, media hash and recovered quotations. A video's legal payer remains
separate from its authorized candidate: an NRCC-paid, candidate-authorized execution is
classified as party-sponsored, not candidate-paid.
Local speech and frame OCR remain unchanged, including possible name or negation errors.
These records use `publisher_post_date`, not an asserted first release or paid-delivery date.
Recovered originals without a verified date remain text-complete in the media backlog and
outside dated comparison denominators. Existing acquisitions are preserved on replay.

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
Explicitly reviewed campaign/ballot-name aliases are bound to actual FEC candidate IDs
in `data/snap-candidate-aliases.json`; they do not overwrite the FEC roster or recognized text.
The same reviewed aliases support federal identity checks for the two new written archives.
For scope qualification only, name matching may span adjacent OCR lines within one frame or
continuous speech cues, never different frames or speech/overlay lanes. The matched context,
frame time, candidate IDs and any reviewed alias evidence are exported. A sole mentioned race
is retained as context, not a validated target assignment. Lexical analysis keeps its stricter
independent-overlay boundaries.
Identity-sensitive creatives have individual reviews in `data/snap-scope-reviews.json`,
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

Time charts use the earliest publisher release/post, reported Google delivery or scheduled Snap start
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

There is **no representative held-out human semantic evaluation**. Contextual portrayal counts
below are exploratory AI-assisted annotations, not validated human prevalence estimates.
Model-accuracy, semantic main-issue, national strategy and persuasion claims remain withheld.

### Context-coded descriptions of people

The previous `mention-lexicon-1` nearby-adjective analysis is retired from the report,
figures and article editions. A word about violent crime or a better policy is not
automatically a description of a candidate mentioned nearby.

`data/portrayal-codebook.json` defines symmetric frames for ability, integrity, interests,
ideology, connection, leadership, independence, record, safety/rights, background and other
personal description. AI-assisted reviewers read complete recovered messages, not
keyword-selected snippets. Each saved decision states reviewed/uncertain and retains
the actual target, party identity basis, person/collective distinction, supported/opponent
role, tone, frame, voice, literal phrase, supporting passage and target anchor.
No attributable descriptions is an explicit reviewed outcome, not a neutral portrayal.
Attribution includes concrete conduct and records, but excludes an issue merely occurring
near a person. Simple fundraising, approval, candidacy and endorsement without a stated
quality are not personal descriptions. ASR/OCR wording is never silently repaired.
The record frame includes attributed actions and policy pledges. A promised outcome
is a commitment in the ad, not evidence that the candidate achieved it.

The main comparison is D-aligned ads describing R people versus R-aligned ads describing
D people. Self/supported candidates form a separate scope. Same-party primary opponents,
collective-party references, unknown target parties and unclear roles cannot silently
enter the cross-party-person comparison. Party identity comes from candidate metadata,
explicit text or a reviewed national-figure crosswalk, never hostility. Endorsed narration
and explicitly adopted clips count; quoted opponents, rebutted accusations and unclear
voices remain downloadable but do not enter headline rates. An opponent can receive
sincere praise: role and valence are independent.

Reviews in `data/portrayal-reviews.json` bind frozen input IDs, sponsor, alignment, original
source hash and exact raw-text hash. Literal offsets are checked at application and validation.
Identical raw text can inherit a review only with matching sponsor and alignment; normalized
message identity alone is insufficient. A changed publisher-page hash with identical text
preserves the original review hash and exposes `source_hash_changed`; changed text, sponsor
or alignment withholds the old review as stale. New inputs remain unreviewed. Automatic
refresh and reproducible builds do not call a model or automatically assign missing labels.

After filters and exact party/message deduplication, review coverage reports reviewed,
uncertain, unreviewed and stale counts. Only reviewed messages with an endorsed description
in the chosen scope form tone/frame denominators. The report separately shows the number
with/without that description among reviewed messages. Negative only, positive only, mixed
(at least one of each), and neutral only are exclusive. Neutral facts alongside a negative
or positive description do not create mixed tone. Inclusive any-negative and any-positive
rates both include mixed messages and overlap. Frames count a message at most once each
and overlap. Every rate retains numerator IDs and denominator counts; zero denominator
is missing evidence, not 0%. Rates describe target portrayals, not general emotional tone.

Recovered partial reviews receive a separate repair pass for roles, literal evidence,
party attribution, quotations and valence. This AI-assisted second pass is **not**
independent human gold. Literal/hash validation establishes evidence integrity, not
semantic accuracy. Illustrations are selected deterministically from the three most
frequent frames per party/scope, preferring repeated exact descriptor phrases, then
shorter passages and ad IDs; no message repeats within a scope. They are illustrations,
not random samples or an intensity ranking.
### Figures and unpublished article editions

`analyze` and `build` generate eleven restrained, 200-DPI **PNG-only** research figures with
CSV/JSON source data in `outputs/figures/`. Missing denominators remain missing, not zero;
monthly plots stop at the actual saved cutoff rather than showing future months as zeros.
Full-snapshot figures do not change with interactive dashboard filters. Sponsor/publisher
grouping combines matching names across collection-source IDs, not inferred legal payers;
the dashboard's collection-source filter still selects acquisition IDs.
Person-portrayal percentage bars share a zero-to-100% scale across parties, with direct
counts and denominators. Supporting lexical bars use labeled data-dependent bounds.
Sensitivity panels share one scale.
Each PNG and CSV has a SHA-256 in the figure manifest. Build/validation also verifies
chart-data hashes, recomputes the research metrics and context-coded portrayals from the corpus,
and checks both article editions and technical reports against the shared findings.

The shared narrative in `outputs/article-data.json` generates Substack Markdown
(`outputs/substack.md`) and The Margin of Error HTML (`outputs/themarginoferror.html`).
Both carry the same snapshot, numerators, denominators, checked illustrations and PNGs.
The local website build stages a matching `article.html`, with local complete-evidence links.
Neither build nor scheduled research refresh uploads to Substack or deploys the website.
The Markdown's relative images/evidence links require authorized hosting and image uploads
before any future publication; no live destination is claimed.

## Interpretation

Source, race, sponsor, date, and extraction mixes differ by party. The first release pilot
particularly overrepresented Democratic House and Republican Senate material. Added outside
groups broaden coverage without eliminating bias. Use race/chamber/source filters and read
individual ads; even within-Senate comparisons are not automatically like-for-like.

The project does not verify claims, infer intent/voter beliefs, estimate persuasion, or turn
incompatible impression/spending ranges into precise exposure. Complete selected-record CSV/JSON
uses the charts' filter scope. Spreadsheet-sensitive cells receive an apostrophe prefix;
JSON retains exact original text.
