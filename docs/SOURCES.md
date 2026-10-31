# Free-source capabilities

Verified October 31, 2026; collection cutoff October 30. Live acquisition status accompanies each snapshot.
This is a source-limited collection of releases and native platform creatives, not a census.

**Publication withdrawn:** the page, report, data downloads, preview, interactive-analysis card
and sitemap entry were removed and verified live. The host integration was removed, and the
daily automatic evidence refresh updates this research repository only. Research evidence
may be pushed without updating the website; publication and host restoration still require
explicit authorization. The final scope cutoff is November 4, 2026, inclusive; the saved
snapshot's actual October 30 cutoff is distinct from that final scope limit.

## Arizona/Kentucky expansion of the October 30 snapshot

The latest acquisition contains **1,868 text records**, including **1,830
English records: 1,226 D / 565 R / 31 other / eight unresolved**. Two
additional Republican House ads contribute **66 and 92 literal words**.
Both are **partial quotations**, not complete transcripts, and remain
semantically **unreviewed**. All **1,866 preceding acquired objects**,
**1,828 preceding analyzed objects**, **27 earlier acquisition reviews**
and **17 protected canonical JSON inputs** are unchanged. Concurrent
frozen claims work was not touched.

Exact observed-text messages are **1,204 D / 528 R**. English House
coverage is **698 D / 187 R**: 476 D / one R Snap and 222 D / 186 R
non-Snap. These are collection counts, not national advertising prevalence.
Neither individual original-video ID nor observed text duplicates an
earlier acquisition, after normalizing YouTube link variants.

| Reported advertiser | Recovered ad | Publisher / report date | Recovered words |
|---|---|---|---|
| NRCC | Amish Shah attack, AZ-01 general | Amy Curtis, Townhall / July 22 | Two passages, 66 words |
| Restore Freedom PAC, Hold the Line PAC project | Massie support / Gallrein attack, KY-04 primary | John Riley, Metro Weekly / May 18 | Six narrator passages, 92 words |

The AZ-01 report explicitly identifies Democratic nominee **Amish Shah,
H4AZ01194 / C00836502**, and Republican opponent Jay Feely. Advertiser
alignment/type follow the **NRCC: R / party**, not Shah's Democratic
registration. Preserve the printed ellipsis, terminal comma and original
wording. Shah's other speeches and clips, election-night commentary and
the following NRCC spokesperson statement are not this ad's words.

The KY-04 report explicitly identifies the May 19 Republican primary.
Supported **Thomas Massie, H2KY04121 / C00509729**, and opponent **Ed
Gallrein, H6KY04171 / C00923995**, are both REP, KY-04. This same-party
attack is not a Republican ad attacking Democrats. Advertiser alignment/
type are **R / outside_group**. The six recovered narrator passages exclude
a separate four-word on-screen label, Singer's archival quoted clip and
reporter assessments. The actual linked `holdthelinepac.com` is distinct
from a differently aligned similarly named `.org` organization.

Both original-video associations come from publisher HTML; no YouTube,
caption service or licensed creative catalog was requested. Sponsor and
project relationships are publisher-reported, not independently inspected
closing-payer disclaimers. Entire decoded HTML SHA-256, unique primary h1,
exact title/date, candidate/race/advertiser/contest context, individual
association and ordered literal passages are bound by the existing
reviewed-release collector. No extraction logic, alias or semantic label
changed.

```sh
political-ads collect --source nrcc-townhall \
  --source holdtheline-metroweekly --until 2026-10-30 --offline
political-ads parquet
political-ads build
political-ads validate
political-ads audit-strategy
```

Independent checks reconcile complete analysis/browser/built JSON,
decompressed gzip and text-complete CSV, all **1,868 Parquet rows** and
eleven visually inspected PNG sets. Network-forbidden isolated replay
reproduces all **523 written records and source states** from the preceding
521 records using exactly **two cached publisher responses**, with the
actual October 31 observation/check date and unchanged October 30
eligibility cutoff. Final affected tests pass **150 cases**; Python
lint/format, frontend lint, **17 frontend tests**, production build and
**seven browser cases** pass. The immediately preceding checkpoint's full
Python suite passed **362 tests**; no production behavior changed here.
Publication validation and independent auditing pass **20 metric groups /
ten chart rows**. Snapshot:
`08a5357d0c85d3467484f673dde4fdc3f0ea25ad2927b3b24e6db3359ae545cf`.
Both editions remain unpublished.

Expanded FactCheck.org discovery follows the article's actually exposed
single-post JSON link and public taxonomy links. Its **2026-ads** archive
returns **34 reports**, not 34 acquired ads. The October 8 tax-ad report
quotes a separate Safety and Affordability PAC attack on **Bob Brooks,
H6PA07188 / C00917096, PA-07**, and associates it with one individual
public viewer URL. That remains an **unadmitted lead**, distinct from the
unresolved CLF/Brooks creative. No viewer, API, catalog, account or media
request was made to the monitoring provider. The report's three other
viewer associations concern Senate races, not House ads. Continue checking
the publisher's actual ad passages and contest identities; do not turn
archive counts, former House offices or reporting prose into House texts.
Denied 13News Now, WAVY and RealClearPolitics pages remain untouched.
Recurring acquisition stays active; publication and host restoration stay
on hold.

## Earlier RJC expansion of the October 30 snapshot

The latest acquisition contains **1,866 text records**, including **1,828
English records: 1,226 D / 563 R / 31 other / eight unresolved**. Two
additional Republican outside-group House ads contribute **15 and 47
literal quoted words**, respectively. Both remain **partial quotations**
and semantically **unreviewed**. All **1,864 preceding acquired objects**,
**1,826 preceding analyzed objects**, **25 earlier acquisition reviews**
and **17 protected canonical JSON inputs**, including native partitions,
candidate identities and saved semantic reviews, are unchanged. Concurrent
frozen claims work was not touched.

Exact observed-text messages are **1,204 D / 526 R**. English House
coverage is **698 D / 185 R**: 476 D / one R Snap and 222 D / 184 R
non-Snap. These are source-limited collection counts, not national
advertising prevalence. Each new record has a different individual media
association and observed-text identity; neither is a certified full
transcript or independently established complete message family.

| Reported advertiser | Recovered ad | Publisher / report date | Recovered words |
|---|---|---|---|
| RJC Victory Fund | Fitzpatrick support / Harvie attack, PA-01 general | Jewish Insider / October 17 local, October 18 UTC | Two fragments, 15 words |
| RJC | Gallrein support / Massie attack, KY-04 primary | Jewish Insider / March 10 | Two passages, 47 words |

Credit: **Marc Rod, Jewish Insider**. The PA-01 report explicitly names
the Victory Fund and links an individual 30-second YouTube ad. Its quoted
label retains the publisher's **Harvey** spelling and terminal comma;
the quoted ending uses **Harvie**. Neither spelling is silently repaired.
The visible byline and public WordPress local timestamp say October 17;
HTML publication metadata says October 18 UTC. Both observations are
retained. The report's announced Sunday launch does not independently
establish first paid delivery. Exact saved FEC identity is **H6PA08277 /
C00607416**, Brian Fitzpatrick, REP, PA-01.

The KY-04 report explicitly describes the May 19 Republican primary and
quotes the RJC ad. Gallrein is **H6KY04171 / C00923995**, and Massie is
**H2KY04121 / C00509729**; both are REP, KY-04. A same-party Republican
target must not become a Democratic opponent. The individual association
is the report's linked **Massie campaign repost of the RJC ad**, not an
asserted first uploader or Massie-produced original. Its first quotation
retains the publisher's terminal comma. This report names RJC, not a
verified Victory Fund legal payer.

RJC CEO press statements, Massie's fundraising reply, Gallrein's
separately linked statement, the unnamed Trump-linked PAC, a separate
Massie ad and reporter assessments remain outside these ad texts.
Advertiser alignment/type are **R / outside_group**. Sponsor attribution
is publisher-reported; neither closing-payer card was independently
inspected. No YouTube, X, caption service, denied RJC archive or licensed
catalog was requested. Full HTML or rendered-content SHA-256, exact
title/date, candidate/advertiser/phase context, individual association
and literal passage order remain bound by the existing reviewed-release
collector. No extraction logic, alias or semantic label changed.

```sh
political-ads collect --source rjc-vf-jewishinsider \
  --source rjc-jewishinsider --until 2026-10-30 --offline
political-ads parquet
political-ads build
political-ads validate
political-ads audit-strategy
```

Independent preservation checks reconcile complete analysis/browser/built
JSON, decompressed gzip and text-complete CSV, all **1,866 Parquet rows**
and eleven visually inspected PNG sets. Network-forbidden isolated replay
starts with the preceding **519-record written corpus** and reproduces
all **521 records and source states** from exactly **two cached publisher
responses**, using their actual October 31 observation/check date without
advancing the October 30 eligibility cutoff. Source/collector regressions
pass **150 tests**, and the full Python suite passes **362 tests**.
Python lint/format, frontend lint, **17 frontend
tests**, production build and **seven browser cases** also passing.
Publication validation and independent auditing pass **20 metric groups /
ten chart rows**. Both article editions remain unpublished.

Broader discovery resolved the previously missing Kiggans original
fact-check URLs, but direct 13News Now retrieval returned **403**. The
second same-host lead was not requested after that denial. WAVY and
RealClearPolitics also returned **403**, with no retries or alternate
retrieval of the denied pages. A public Townhall report supplies a new
NRCC AZ-01 quotation and individual original-video association that
were subsequently admitted in the Arizona/Kentucky checkpoint above. JTA's separate
pro-Massie report supplies quoted ad words but no individual original
association; its linked advertiser's issues page contains policy prose,
not recovered advertising. Independent Metro Weekly reporting links an
individual pro-Massie creative and quotes its narration; that is another
acquisition lead subsequently admitted above. They were not counted in this
earlier RJC snapshot.
Continued discovery and recurring acquisition remain active; publication
and host restoration stay on hold.

## Earlier NC-11 expansion of the October 30 snapshot

The preceding acquisition contains **1,864 text records**, including **1,826
English records: 1,226 D / 561 R / 31 other / eight unresolved**. Two
additional **NRCC-funded, publisher-reported NC-11 ads** contribute actual
quoted ad words, not press statements, social captions or reporting prose.
All **1,862 preceding acquired objects**, **1,824 preceding analyzed
objects**, 23 earlier acquisition reviews and **17 protected canonical
JSON inputs**, including native partitions, identities and saved semantic
reviews, are unchanged. Both additions remain **partial quotations** and
semantically **unreviewed**.

Exact observed-text messages are **1,204 D / 524 R**. English House
coverage is **698 D / 183 R**: 476 D / one R Snap and 222 D / 182 R
non-Snap. These collection counts do not estimate national ad prevalence.
Distinct original-video links and observed-text identities establish two
new records here, not independently certified complete message families.

| Reported advertiser | Recovered ad | Publisher / report date | Recovered words |
|---|---|---|---|
| NRCC | Mom, Jennifer Balkcom NC-11 | NC Newsline / September 30 | Seven fragments, 51 words |
| NRCC | Barn-dance attack on Jamie Ager, NC-11 | Cardinal & Pine / October 27 | Two passages, 24 words |

Credit: **Christine Zhu, NC Newsline**; **Cardinal & Pine, credited to USA
Today Network via Reuters Connect**. Each report explicitly identifies
the advertised NC-11 contest, reports NRCC funding and links a different
individual YouTube creative. Advertiser alignment/type are **R / party**,
not inferred candidate-committee payment. Neither video nor a caption
provider was requested; no closing-payer card was independently inspected.
Exact saved FEC identity is **H6NC11321 / C00958785**, Jennifer Balkcom,
REP, NC-11. No roster refresh, new alias or fuzzy match was needed.

Mom retains only literal fragments of Balkcom and her mother's ad speech,
including the publisher's singular *lower cost* and punctuation. Its
three-word opening fragment is not a complete opening sentence. Ager's
separate Barn Dance, NRCC/DCCC statements and the political scientist's
analysis remain outside the Republican text. AOL separately reports a
September 29 video posting; the admitted original report's September 30
date remains authoritative for this record, not verified paid delivery.

The attack ad retains only the narrator's two quoted passages. They are
not authentic Ager statements, campaign responses, LGBTQ+ community
responses or the publisher's fact-checking. Reported synthetic imagery
does not become an independently checked factual or semantic label.
October 27 is the report date, not independently verified first release.
The full decoded HTML hashes, exact titles/dates, federal identity,
advertiser context, individual-media associations and ordered literal
passages are checked by the existing fail-closed reviewed-release path.

```sh
political-ads collect --source nrcc-ncnewsline \
  --source nrcc-cardinalpine --until 2026-10-30 --offline
political-ads parquet
political-ads build
political-ads validate
political-ads audit-strategy
```

Independent preservation checks reconcile complete analysis/browser/built
JSON, decompressed gzip and text-complete CSV, all **1,864 Parquet rows**
and eleven PNG sets. Network-forbidden isolated replay starts from the
preceding **517-record written corpus** and reproduces all **519 records
and source states** using only **two cached HTML responses**. It replays
the recorded original-observation and subsequent cached-check dates;
crossing midnight does not rewrite first observation or advance the
October 30 eligibility cutoff. This clock-bound replay is distinct from
an ordinary new check whose status uses the actual current date.

Final checks pass **362 Python tests**, Python lint/format, frontend
lint, **17 frontend tests**, the production build and **seven browser
cases**. Publication validation and the independent strategy audit pass
**20 metric groups / ten chart rows**. All eleven updated PNGs were
visually inspected. Both article editions remain unpublished.

Broader PA-01 discovery found a distinct **RJC Victory Fund ad quotation**
in Jewish Insider's October report. Its public 2026 RJC search returned
**56 posts**, also identifying a separate **KY-04 RJC primary ad**
supporting Ed Gallrein and criticizing Thomas Massie. Both were unadmitted
at this checkpoint and are recovered in the RJC expansion above; search
results and RJC press statements themselves are not new ads.
WHYY's October 15 report supplies a long quoted **Patch post**, not a
verified ad transcript, and no individual ad association. That post is
not counted as ad speech. Original Kiggans fact-check URLs were unresolved
at this checkpoint; the subsequent access result is recorded above.
Continued discovery and recurring acquisition stay active;
website/Substack publication and host restoration remain on hold.

## Earlier publisher-linked expansion of the October 30 snapshot

The preceding acquisition checkpoint contains **1,862 text records**, including **1,824
English records: 1,226 D / 559 R / 31 other / eight unresolved**. It adds
five Republican House ad records in **OH-07, NM-02, AZ-01 and AZ-06**, all
explicitly retained as **partial quotations**, not complete transcripts.
All **1,857 preceding acquired objects**, **1,819 preceding analyzed
objects**, eighteen earlier acquisition reviews and saved semantic reviews
are unchanged. The additions remain semantically **unreviewed**.
Exact observed-text message counts are **1,204 D / 522 R**. English House
coverage is **698 D / 181 R**: 476 D / one R Snap and 222 D / 180 R
non-Snap. These are source-limited collection counts, not national advertising
prevalence or independently certified complete creative/message families.

| Reported advertiser | Recovered ad | Publisher / report date | Recovered words |
|---|---|---|---|
| Max Miller and NRCC, reported coordinated ad | Socialist, OH-07 | American Journal News / September 16; linked Big AL public player | One passage, 89 words |
| Greg Cunningham and NRCC, reported joint ad | Barbershop, NM-02 | American Journal News / October 9; linked Washington Examiner report / September 25 | Two passages, 27 words |
| Safety and Affordability PAC | Attack on Amish Shah, AZ-01 | American Journal News / October 20 | Five fragments, 22 words |
| Congressional Leadership Fund | Mendoza tax comments, AZ-06 | American Journal News / September 11 | Two passages, 23 words |
| Juan Ciscomani campaign | Separate ad using the same Mendoza clip, AZ-06 | American Journal News / September 11 | One shared clip, 15 words |

Credit: **Jesse Valentine, American Journal News**; **Lauren Green,
Washington Examiner**; and the explicitly publisher-linked **Big AL public
player**. Broader public WordPress discovery inspected all **218 matching
2026 posts across three pages**, not just the eleven posts returned by two
exact-phrase queries. The `bigal.media` search returned one report. These
are bounded publisher-query results, not complete national discovery.

The two linked-text recoveries bind **both complete response SHA-256
hashes**, not merely the original report. The main article must identify
the exact candidate, advertiser, date/title and media association, and must
literally link the secondary page. Only the supported public Big AL player
or the linked Washington Examiner congressional report can supply secondary
text. Its own hash, explicit ad context, exact federal identity and unique
reviewed element are checked before literal ordered quotations are admitted.
Changed or ambiguous evidence fails closed. These remain partial quotations;
the secondary selector cannot turn them into a claimed complete script.

The Miller player publicly exposes its transcript without login. The
**Negative Ad** label, specifications and September 7 upload date are player
metadata, not ad words or an adopted semantic judgment. The complete HTML
hash includes incidental expiring media markup and is not weakened to make
future changes pass. Only the public HTML page was requested: **no login,
API, catalog, embedded credential, signed storage URL or original video**
was used. The recorded September 16 report date is distinct from the
player's reported September 7 upload; neither proves first paid delivery.
The displayed text is not an independently checked complete audio/on-screen
transcript or closing-payer inspection.

The Cunningham report explicitly links both the individual Barbershop video
and the September 25 Washington Examiner story about that same creative.
The latter supplies two quotations from the men conversing in the ad and
reports production with NRCC. Its ordinary visible HTML was sufficient;
no login, subscription or paywall workaround was used. October 9 remains
the primary report date, while the earlier September 25 report is retained
in provenance: this is **not** a newly released October 9 advertisement.
Candidate and NRCC press responses are not imported as ad words. Neither
reported campaign/party attribution independently establishes a sole legal
closing payer.

The Arizona reports' exact legacy AdImpact `/admo/viewer/<UUID>` links
are recognized **as associations only**; no AdImpact page, API, account,
catalog, credential or media was requested. The Safety and Affordability
advertisement is Republican-aligned by the reported organization's
Trump/MAGA Inc. connection, not by its Democratic target's party. Its
several short fragments remain **one** incomplete ad, not several creatives
or automatically assigned descriptions of Shah. Exact federal identities
are **H2OH16051 / C00770818** (Miller), **H6NM02127 / C00921791**
(Cunningham), **H4AZ01194 / C00836502** (Shah, the Democratic target),
and **H2AZ02360 / C00786194** (Ciscomani). No new alias or fuzzy matching
was introduced.

The CLF and Ciscomani records have **different reported advertisers and
different individual media associations**, but explicitly share the same
15-word Mendoza clip. Only CLF's record includes its separately attributed
eight-word voiceover. The campaign record does not inherit that narration
or the longer original-forum quotation. Their different observed-text
identities do not certify unrelated full-message families. Publisher
fact-checking, editorial assessments and reported press statements remain
outside ad text and semantic analysis.

```sh
political-ads collect --source miller-americanjournal \
  --source cunningham-americanjournal \
  --source safety-affordability-americanjournal \
  --source clf-americanjournal --source ciscomani-americanjournal \
  --until 2026-10-30 --offline
political-ads parquet
political-ads build
political-ads validate
political-ads audit-strategy
```

The two secondary-text cases failed before the collector extension; two
legacy-viewer association cases also failed before their narrow recognition
fix. Focused regressions reject unlinked or unsupported pages, login/catalog
paths, deceptive hosts, changed hashes, missing context/identity, missing or
ambiguous selectors, quotations outside the selected element, and claimed
full-script completeness. These changes do not relax existing primary
publisher, exact candidate, article heading/date or quotation checks.

Network-forbidden isolated replay reproduces all **517 written objects and
source states** from the preceding 512-object corpus using only **six**
cached responses, including both secondary pages and the shared CLF/campaign
report. All **362 Python tests**, Python lint/format, frontend lint,
**17 frontend tests**, production build and **seven browser cases** pass.
Independent auditing verifies **20 metric groups and ten chart rows**.
Complete analysis/browser/production JSON, gzip and CSV agree; all **1,862
Parquet identity/text/hash/alignment rows** and eleven visually inspected
PNG sets reconcile. Every preceding acquired/analyzed object, all eighteen
earlier acquisition reviews and saved semantic reviews remain unchanged.

Further discovery does not count as acquired text. Barrett's verified
campaign homepage exposes a B-roll video and channel, not the health-care
creative. A Semblen race page exposes third-party Meta-ad excerpts, but its
terms prohibit bulk automated copying; no dataset, model output or archive
from that service is imported, and no account or trial is started. Its
primary-campaign link is useful discovery, not permission to copy a catalog.
Ordinary campaign biography, B-roll and secondary paraphrases remain
excluded. Acquisition continues through other public primary/publisher
routes; website and both article editions remain unpublished.

## Preceding three-state expansion of the October 30 snapshot

That acquisition contains **1,857 text records**, including **1,819
English records: 1,226 D / 554 R / 31 other / eight unresolved**. It adds
three Republican House advertisements from **ME-02, AZ-06 and NV-02**,
each explicitly retained as **partial quotations**, not a recovered full
transcript. All **1,854 preceding acquired objects**, **1,816 preceding
analyzed objects**, fifteen earlier acquisition reviews and saved semantic
reviews are unchanged. The additions remain semantically **unreviewed**.
Exact-message counts are **1,204 D / 517 R**. English House coverage is now
**698 D / 176 R**: 476 D / one R Snap and 222 D / 175 R non-Snap. These
are source-limited collection counts, not national advertising prevalence.

| Reported advertiser | Recovered ad | Publisher / report date | Recovered words |
|---|---|---|---|
| Paul LePage campaign, ME-02 | Immigration | Mediaite / September 24 UTC, September 23 EDT | Two passages, 26 words |
| Juan Ciscomani campaign, AZ-06 | Veteran testimonial | Townhall / October 16 | Three passages, 46 words |
| David Flippo campaign, NV-02 | Benitez-Thompson criminal-release allegation | American Journal News / October 20 | Two passages, 24 words |

Credit: **Kathryn Wilkens, Mediaite**; **Joe Chalfant, Townhall**; and
**Jesse Valentine, American Journal News**. Each entry in
`data/ad-release-reviews.json` binds the actual publisher URL/title/date,
complete response SHA-256, exact public ad-post association, advertiser
context, exact FEC identity and literal ordered passages. All three messages
and their exact status associations are absent from the preceding corpus.
Several quotations from one ad remain one record. Publisher punctuation,
including an ellipsis in the Ciscomani passage, is not silently reconstructed.

This expands association recognition, not X acquisition. HTTPS individual
`/handle/status/<15-20-digit-ID>` links on exact X/Twitter hosts are recognized;
profiles, feeds, deceptive hosts, malformed IDs and extra path components
are rejected. Four previously failing host cases now pass, alongside a
negative-case regression. No X page, caption service or disclosure catalog
was accessed. The LePage and Ciscomani reports link campaign posts; the
Flippo report links a **journalist's** post. That distinction remains in the
evidence; none is represented as downloaded original media, independently
inspected closing-payer proof or verified paid delivery.

LePage's machine timestamp, **September 24 at 01:28:41 UTC**, and visible
**September 23 evening EDT** refer to the same instant. His record uses the
metadata's UTC date and retains the local/post dates in provenance; this is
not a second release or an inferred first airing. Exact 2026 FEC identities
are **H6ME02148 / C00904094** (LePage), **H2AZ02360 / C00786194**
(Ciscomani), and **H4NV04108 / C00901710** (Flippo). Flippo's current
district follows the roster's NV-02 field, not his historical candidate-ID
digits. No new alias or fuzzy matching was introduced.

Advertiser alignment follows the reported campaign, not the news publisher,
opponent or testimonial speaker. In particular, Ciscomani's self-described
Democratic testimonial speaker does not make the ad Democratic. His election
phase remains **unknown**, because this report does not explicitly establish
the general-election contest; October timing alone is insufficient. The
LePage and Flippo reports explicitly identify their Democratic opponents.
Social captions, press-conference remarks, quoted campaign statements,
biographies, reporter commentary and fact-checking remain outside ad text.
Acquisition does not verify the allegations or supply a semantic tone label.

```sh
political-ads collect --source lepage-mediaite --source ciscomani-townhall \
  --source flippo-americanjournal --until 2026-10-30 --offline
political-ads parquet
political-ads build
political-ads validate
political-ads audit-strategy
```

Network-forbidden isolated replay reproduces all **512 written objects and
source states** from the preceding 509-object corpus using only the three
exact cached responses. All **346 Python tests**, Python lint/format,
frontend lint, **17 frontend tests**, production build and **seven browser
cases** pass. Independent auditing verifies **20 metric groups and ten chart
rows**. Complete analysis/browser/production JSON, gzip and CSV agree; all
**1,857 Parquet identity/text/hash/alignment rows** and eleven visually
inspected PNG sets reconcile. Saved portrayal reviews and every preceding
acquisition/analyzed object remain unchanged.

The public American Journal News archive's bounded 2026 Flippo query exposes
two posts: the admitted October 20 ad report and an October 15 campaign-support
report without recovered ad copy. The latter is not counted. Earlier search
leads are not substituted for actual publisher evidence. Recurring acquisition
continues, while website and both article editions remain unpublished.

## Preceding October 30: two North Carolina Republican House ad quotations

That acquisition contains **1,854 text records**, including **1,816
English records: 1,226 D / 551 R / 31 other / eight unresolved**. It adds
two distinct Laurie Buckhout campaign ads in **NC-01**, both **partial
quotations**, not full recovered transcripts. All **1,852 preceding acquired
objects**, **1,814 preceding analyzed objects** and saved semantic reviews
are unchanged. Both additions remain semantically **unreviewed**.
Exact-message counts are **1,204 D / 514 R**. English House coverage is now
**698 D / 173 R**: 476 D / one R Snap and 222 D / 172 R non-Snap. This
remains a source-coverage imbalance, not national party advertising prevalence.

| Reported advertiser | Recovered ad | Original publisher / report date | Recovered words |
|---|---|---|---|
| Laurie Buckhout campaign | Show Up | The North State Journal / September 1 | Two literal passages, 29 words |
| Laurie Buckhout campaign | Veterans and family | The Center Square / September 15 | Four literal passages, 46 words |

Credit: **A.P. Dillon, The North State Journal**, and **Alan Wooten, The
Center Square**. Each review in `data/ad-release-reviews.json` binds the
original article URL/title/date, exact public response SHA-256, advertiser
context, original-video association and literal passages. Both video IDs and
both exact messages are absent from the preceding corpus. Multiple passages
within one ad remain one record. Speaker punctuation, including trailing
commas, is retained rather than reconstructing omitted words.

The North State Journal article exposes its public WordPress post endpoint.
Only two quotations explicitly attributed to Show Up are admitted; campaign
statements, voting-record reporting and a tiny isolated phrase are excluded.
The Center Square article links a different original ad. Its four admitted
passages comprise the child's opening question, a reported on-screen caption,
and two candidate-voice quotations; the surrounding biography, district
analysis and reporter narration are excluded.

The Wilmington Standard syndication displays **September 14**. Following its
original-publisher link establishes **September 15** on The Center Square,
with matching machine timestamp and Tuesday-release context. The original
is authoritative; the discrepant mirror is neither a separate acquisition
nor the date source. The original has navigation headings before the story
and an abbreviated visible date. Reviewed selectors must uniquely identify
the actual article `h1` and publication element; an explicit date format
parses `Sep 15, 2026`. Visible dates must agree with publication metadata and
any selected element's `datetime` attribute. Full-response hashes remain
strict: dynamic HTML changes require renewed acquisition review.

Both records use exact FEC candidate **H4NC01137**, Laurie Buckhout, REP,
House NC-01, principal committee **C00853499**. No alias or fuzzy identity
match was added. General-election phase follows the explicit contest against
Democratic incumbent Don Davis, not the calendar alone. Advertiser attribution
follows the campaign identified by the reporting; closing legal payers and
paid-delivery dates were not independently inspected or established.

```sh
political-ads collect --source buckhout-nsj --source buckhout-centersquare \
  --until 2026-10-30 --offline
political-ads parquet
political-ads build
political-ads validate
political-ads audit-strategy
```

Isolated network-forbidden replay reproduces all **509 written objects and
source states** from the preceding 507-object corpus using only the two exact
cached responses. All **341 Python tests**, Python lint/format, frontend lint,
**17 frontend tests**, production build and **seven browser cases** pass.
Independent auditing reconciles **20 metric groups and ten chart rows**.
Complete JSON/gzip/CSV exports reconcile across analysis, browser and production;
all **1,854 Parquet identity/text/hash/alignment rows** and all **eleven PNG
copies** agree.

Broader Florida searches encountered **HTTP 402** on Florida Politics articles;
those articles were not retried through alternative routes, and snippets or
audio links were not counted as recovered ads. Other campaign and public-video
leads remain unacquired without verified ad words and associations. No paused
caption provider was retried. Recurring acquisition continues; both article
editions and the website remain unpublished.

## Preceding October 30: eight marked Republican House scripts from New Jersey Globe

That acquisition contains **1,852 text records**, including **1,814
English records: 1,226 D / 549 R / 31 other / eight unresolved**. It adds
eight Republican House scripts, not eight newly discovered districts or a
representative national sample. All **1,844 preceding acquired objects** and
saved semantic reviews are preserved. The eight additions remain semantically
unreviewed; acquisition review does not supply tone or strategy judgments.
Exact-message counts are **1,204 D / 512 R**. English House coverage is now
**698 D / 171 R**: 476 D / one R Snap and 222 D / 170 R non-Snap.

| Reported advertiser | Ad | Report date | Federal race |
|---|---|---|---|
| American Action Network | SALT deduction issue-advocacy ad | August 14 | Kean, NJ-07 |
| Tom Kean Jr. campaign | Every Patient | August 26 | NJ-07 |
| Tom Kean Jr. campaign | Proud | September 2 | NJ-07 |
| Tom Kean Jr. campaign | Accountable | September 4 | NJ-07 |
| Tom Kean Jr. campaign | Profits Over Patients | October 8 | NJ-07 |
| Tom Kean Jr. campaign | Conversation | October 20 | NJ-07 |
| New Jersey Republican State Committee | Two-Faced | October 21 | Kean, NJ-07 |
| Joe Hathaway campaign | First special-general-election digital ad | March 19 | NJ-11 |

Credit: **New Jersey Globe**, whose original article URL, exact public post
response, report date, marked script and advertiser attribution are bound in
each `data/ad-release-reviews.json` entry. Only ad words enter the corpus, not
the articles, policy explanations, spokesperson quotations or reporter
assessments. Each record links the original article and the separately embedded
original-ad association. The publisher's [terms](https://newjerseyglobe.com/terms-conditions/)
specify permission or credit for reuse; publisher credit and provenance remain
in the complete exports.

Discovery followed the publisher's disclosed public WordPress API, not an
invented private endpoint. The initial `"TV ad"` and `"Hathaway" "ad"` searches
returned 32 and 103 results across their completed pages, comprising 134
distinct posts. Broader `script` and `transcript` searches returned 104 and six
results, respectively, and exposed the additional AAN script. These are bounded
queries, not exhaustive archive discovery. State/local ads, debates, suggested
campaign messaging and unquoted descriptions of advertisements are excluded.
The October 5 NRCC childcare ad is already acquired as
`nrcc-a9673d0617ba52de-0`; its newly found news reproduction is **not added
again**. The AAN article describes two districts but supplies only one linked,
marked NJ-07 script; no NJ-09 execution is fabricated.

Every review binds the full `content.rendered` SHA-256, post ID, exact article
URL/title/date, required advertiser context, one original-video association,
literal passages and an individually inspected `script_selector`. The selector
must match **exactly one** element, whose explicitly marked script must equal
the complete admitted text. Missing, ambiguous or non-script selections fail
closed. This prevents inline `Script:` paragraphs from absorbing subsequent
reporting without globally truncating genuine multi-paragraph scripts.
Selectors cannot be applied to partial quotations.

The full content hash intentionally retains the video plugin's generated
iframe ID. Archive-list and individual-post responses can therefore differ
despite identical visible words and media links. Admission uses the exact
reviewed individual-post response; no hash normalization or silent approval of
changed HTML occurs. Subsequent changes require renewed acquisition review,
and collection preserves the last good record rather than replacing it.
`--offline` requires those already reviewed cached responses.

Exact 2026 FEC identities are Kean `H0NJ07261`, principal committee `C00703058`,
and Hathaway `H6NJ11211`, principal committee `C00921809`. The adapter now honors
the **existing** reviewed Tom Kean alias of Thomas H. Kean Jr.; it does not add
fuzzy matching or change the roster. A speaker calling himself a Democrat does
not change the Kean campaign advertiser's Republican alignment. The New Jersey
Republican State Committee ad is not attributed to the NRCC. American Action
Network remains a separate outside nonprofit, not Congressional Leadership
Fund. Its legislative thank-you ad retains unknown election phase; Hathaway's
general phase follows the explicit **special general election** context.

Advertisers follow the publisher's attribution and candidate approvals, not
independently inspected sole legal closing payers. `publisher_report_date` is
not verified first release, paid delivery or a delivery interval. Publisher
speaker labels, punctuation and transcription oddities are retained; claims
are not verified findings. No YouTube or paused caption-provider request is
needed.

```sh
political-ads collect --source aan-globe --source kean-globe \
  --source nj-gop-globe --source hathaway-globe --until 2026-10-30 --offline
political-ads parquet
political-ads build
political-ads validate
political-ads audit-strategy
```

An isolated, network-forbidden reconstruction reproduces all **507 written
objects and source states** using only eight reviewed cached responses.
All **1,806 preceding analyzed objects** are unchanged. The implementation
passed the 331-test Python suite; the final eight-record snapshot additionally
passes 138 affected source, collection, analysis, editorial and publication
tests, Python lint/format, frontend lint and all 17 unit tests, the production
build and seven browser tests. Independent auditing reconciles all 20 same-ad
metric groups and ten chart rows. Complete analysis/browser/production JSON,
gzip and CSV exports, all 1,852 Parquet identity/text/hash/alignment rows and
all eleven visually inspected PNGs reconcile. Both article editions remain
unpublished.

The recurring acquisition prompt remains active. Wider House discovery
continues, and website/Substack publication stays on hold.

## Preceding October 30: public House mailers and independently quoted ad words

That snapshot contains **1,844 acquired text records**, including **1,806
English records: 1,226 D / 541 R / 31 other / eight unresolved**. Exact
party/message counts are **1,204 D / 504 R**. English House coverage is now
**698 D / 163 R**, five more Republican House records than the preceding
checkpoint. All **1,839 preceding acquired objects** and saved portrayal reviews
remain unchanged. None of these five additions has a new semantic portrayal label.

| Reported or inspected payer | Candidate/race | Publisher evidence date | Recovered evidence |
|---|---|---|---|
| Defending Main Street Super PAC | Eric Flores, TX-34 | September 29 gallery item | One two-sided endorsement mailer; local image OCR |
| Defending Main Street PAC | Mike Carey / Don Leonard, OH-15 | October 23 gallery item | One two-sided contrast mailer; local image OCR |
| Defending Main Street PAC | Don Leonard, OH-15 | October 23 gallery item | One separate two-sided attack mailer; local image OCR |
| No Going Back | Shomari Figures, AL-02 | October 29 article | Two literal passages from one reported ad; partial quotation |
| Alabama Christian Conservatives | Rhett Marques, AL-02 | October 29 article | One literal passage from a separately reported ad; partial quotation |

Defending Main Street's public [Campaign Support gallery](https://www.defendingmainstreet.com/materials)
exposes 50 items, including three 2026 images and seven 2026 YouTube links.
The images are actual mailers, not video thumbnails; two faces in one original
remain **one record**. Each review binds the full gallery HTML SHA-256/title,
public `wix-warmup-data` script, exact gallery/item ID, `createdDate`, public
original URL and original-byte SHA-256. Secured items and video items are rejected.
`createdDate` is a gallery-item timestamp, represented as
`publisher_gallery_upload_date`, **not independently verified first publication,
campaign airing or paid delivery**. Flores's creative explicitly names the
March 3 election despite its September 29 gallery timestamp; that discrepancy is
retained rather than treating it as a September campaign execution.

The three closing disclaimers were visually inspected. Flores's says **Defending
Main Street Super PAC**; the two Ohio mailers say **Defending Main Street PAC**.
Neither is silently renamed Republican Main Street Partnership. Local OCR is
retained unchanged, including small-print errors, imperfect reading order and an
upside-down disclaimer it does not recover. A redundant OCR attempt for the
Leonard image timed out; its already completed local extraction, bound to the
same original-byte hash, was reused without editing recognized words.

Advertiser alignment is independently bound to Defending Main Street's exact
homepage hash and its explicit Republican-majority electoral program. The
negative-only Leonard image therefore remains **Republican-aligned**, although
its exact named FEC candidate `H6OH15112` is Democratic. The other exact candidate
identities are Flores `H6TX34080` and Carey `H2OH15228`. Target affiliation is not
advertiser affiliation.

[Alabama Public Television's October 29 report](https://aptv.org/apt-news/ad-spending-tops-11m-in-alabamas-fiercest-congressional-race/)
separately identifies the two outside groups, quotes their ads and immediately
embeds a different public viewer for each. Only literal quoted ad words enter
these two records, not the reporter's spending figures, policy explanations,
campaign interviews or adjacent Democratic ads. These are **partial quotations,
not full transcripts or verified claims**. Legal payer names follow the report;
no original closing cards were inspected. Republican alignment follows the
reported advertisers, including when the named target is Democrat Figures
(`H4AL02170`), not the news publisher or target party.

The article body is absent from the publisher's disclosed WordPress response,
so collection uses the public HTML. Its full response hash, exact heading and
uniquely matched visible publication-date selector are reviewed individually.
Missing, ambiguous, changed or conflicting dates fail closed. Only exact
HTTPS `platform.adimpact.com/viewer/<UUID>` links without query credentials
are recognized as associations. **No AdImpact catalog, account, player API or
original media was requested.** The article date is not a first-airing claim.

```sh
political-ads campaign-native --until 2026-10-30 --offline
political-ads collect --source ngb-aptv --source acc-aptv --until 2026-10-30 --offline
```

Isolated cache-only reconstruction reproduces all 89 native objects and all 499
written objects, including source states and attempts. Complete evidence exports,
figures and both unpublished editions are rebuilt together. House composition is
476 D / one R Snap and 222 D / 162 R non-Snap. This remains incomplete,
source-dependent acquisition, not national advertising prevalence.

Local validation passes all 320 Python tests, Python lint/format, frontend lint,
17 frontend tests, the production build and seven browser tests. Independent
auditing reconciles all 20 same-ad metric groups and ten chart rows. Complete
JSON/gzip/CSV exports, all 1,844 Parquet identity/text/hash/alignment rows and all
eleven PNG copies reconcile; the figures were visually inspected. All 1,801
preceding analyzed objects remain unchanged.

Conservatives for American Excellence's separately inspected public homepage and
Winner Highlights page expose candidate links, not additional recovered ad scripts
or original media. The Nevada reporting examples, seven Defending Main Street
YouTube links and other publishers remain leads where actual text is not recovered.
No paused caption provider was retried. The recurring acquisition prompt remains
active; website/Substack publication stays on hold.

## Preceding October 30: wider House recovery through public original media

The snapshot contains **1,839 acquired text records**, including **1,801 English
records: 1,226 D / 536 R / 31 other / eight unresolved**. Exact party/message
counts are **1,204 D / 499 R**. English House coverage is **698 D / 158 R**,
up from 152 Republican House records in the preceding checkpoint. The six
additions are actual recovered words, not discovery-link counts:

| Reported or inspected payer | Candidate/race | Publisher date | Recovered evidence |
|---|---|---|---|
| Lawler for Congress | Mike Lawler, NY-17 | October 20 | Four literal passages, 76 words, from the closing-ad release; one partial record |
| Republican Main Street Partnership | Nick LaLota, NY-01 | March 19 | Original 30-second Fair Share video, speech and frame OCR |
| Republican Main Street Partnership | Andrew Garbarino, NY-02 | March 19 | Separately linked 30-second Fair Share candidate variant |
| Republican Main Street Partnership | Mike Lawler, NY-17 | March 19 | Separately linked 30-second Fair Share candidate variant |
| Republican Main Street Partnership | Blake Moore, FEC UT-02 | June 3 | Original 30-second issue-advocacy video; publisher describes UT-01 |
| Iowans for Zach Nunn | Zach Nunn, IA-03 | August 3 | Candidate-paid original linked by an RMSP release; approximately one minute plus a black tail |

RMSP's public sitemap exposes 331 posts and seven campaign-related release paths.
Three of those releases are dated in 2026; the four older releases are excluded.
The Moore and Nunn releases directly embed Wix-hosted MP4s. The New York release
explicitly links three public Dropbox shares, retrieved using their standard
`dl=1` download option. No blocked caption provider, account API, third-party access
credential or bulk licensed catalog is used. Each of the five originals has a new
byte hash relative to previously acquired native media. The three Fair Share
executions are candidate variants of the same template, not three unrelated
message families.

The closing cards of all five originals were visually inspected. Four name
Republican Main Street Partnership as payer; Nunn's card names **Iowans for Zach
Nunn**, not RMSP. Publisher, campaign target and legal payer are not interchangeable.
Moore's release describes Utah's first district, whereas his exact saved 2026 FEC
identity `H0UT01205` lists district 02. The canonical election race follows that
roster, with both observations and an explicit discrepancy flag retained.

`data/campaign-native-reviews.json` binds each exact release title, publication
metadata and response SHA-256 to its linked original, media SHA-256, exact FEC
candidate identity, inspected payer and literal recovered evidence. The existing
`campaign-native` collector now accepts those individually reviewed dated releases.
Changed or missing release dates/titles/hashes and missing original links fail
closed. Local speech recognition and frame OCR retain their name errors,
incidental background text and imperfect disclaimers; these are **not manually
certified complete transcripts**. New semantic portrayal labels are not invented.
The publisher release dates do not establish first upload, first airing or paid
delivery.

Replay the native additions using the saved original HTTP and local extraction
caches:

```sh
political-ads campaign-native --until 2026-10-30 --offline
political-ads collect --source lawler --until 2026-10-30 --offline
```

An isolated native reconstruction reproduces all acquired objects, source states
and attempts; selected Lawler replay is byte-identical. All **1,833 preceding
acquired records**, saved portrayal reviews and unrelated native partitions are
preserved. The Lawler fallback requires one original video association and groups
explicitly attributed speech into one ad, excluding policy explanations and press
statements. Complete downloads, figures and both unpublished editions are rebuilt
together. House composition is now 476 D / one R Snap and 222 D / 157 R non-Snap.

The gap remains unresolved, not a national advertising-volume estimate or a
collection ceiling. Expanded Wittman, Evans and Buckhout campaign checks did not
yield additional usable text: Wittman's linked ZIP is photographs, and Buckhout's
media kit links channels. Defending Main Street is a separate organization from
RMSP; its campaign materials and American Action Network's releases are continuing
discovery leads, not counted records. The recurring acquisition reminder remains
active. Website/Substack publication stays on hold.

## Preceding October 30: scripts and independently reported ad quotations

The preceding snapshot contained **1,833 acquired text records**, including **1,795 English
records: 1,226 D / 530 R / 31 other / eight unresolved**. Exact party/message
counts are **1,204 D / 493 R**. English Republican House coverage rises from
**149 to 152**, alongside 698 Democratic House records. The additions are:

| Reported advertiser | Candidate/race | Publisher date | Recovered evidence |
|---|---|---|---|
| NRCC | Zach Nunn, IA-03 | April 14 | Complete marked script reproduced by The Iowa Standard |
| Rhett Marques campaign | Rhett Marques, AL-02 | July 14 | Three ad quotations in Yellowhammer News; partial, special primary |
| Marty for Congress | Marty O'Donnell, NV-03 | August 5 | Two passages explicitly quoted from “Tune” by The Nevada Independent; partial, general election |

These are **three additional text records**, not three verified paid deliveries or
independently certified creative executions. Nunn's script is a candidate variant
of an already observed NRCC Tax Day template. The two news excerpts retain
`publisher_ad_copy_completeness_unverified`; no omitted words, intervening narration
or closing payer card are invented. Neither release commentary nor journalists'
policy explanations enter the ad text. All three remain semantically unreviewed,
not neutral or automatically classified as praise/attack.

`data/ad-release-reviews.json` specifies each exact public retrieval URL, source
content SHA-256, publication metadata, original video association, literal
passages in source order, advertiser evidence and exact 2026 FEC candidate ID.
The registered `reviewed_releases` collector rejects changed content, mismatched
dates/titles, missing quotations/media links and nonmatching federal identities.
Marked full scripts must also equal the existing transcript extractor's output.
Failures retain the last-good partition; access denials remain paused. These
sources deliberately report incomplete discovery, rather than suggesting their
whole archives were acquired. Replay just these additions with:

```sh
political-ads collect --source nrcc-iowa-standard --source marques-yellowhammer \
  --source odonnell-nevada-independent --until 2026-10-30 --offline
```

Offline replay requires the saved HTTP cache; the committed ledger and extracted
text are not a substitute for missing original response bytes. Without `--offline`,
the same public URLs are checked against the reviewed hashes. Date basis is
`publisher_report_date`, not verified first airing. O'Donnell's August 5 date
comes from the article's publication metadata, not its discussion of September
reservations. Named campaigns and NRCC are the reported advertisers; a news
publisher's editorial alignment is never assigned to the ad or its legal payer.

All **1,830 prior acquired records and saved portrayal reviews remain unchanged**.
The House composition is now 476 D / one R Snap records and 222 D / 151 R
non-Snap records. This is still an unmatched, source-limited collection, not
national party ad prevalence. Broader campaign galleries and new public archives
were investigated, but video links, ordinary campaign statements, short closing
slogans, state-election ads and CLF's explicitly 2024 gallery were not counted as
new usable federal ad text. Five Driving Force Action House links remain leads.
Complete exports, eleven PNG figures, the report and both unpublished editions
are rebuilt together. Website/Substack publication remains on hold.

## Earlier October 30 House-focused follow-up

The preceding snapshot contained **1,830 acquired text records**, including **1,792 English
records: 1,226 Democratic-aligned, 527 Republican-aligned, 31 other and eight unresolved**.
Exact party/message counts are **1,204 D / 490 R**. English House coverage is now
**149 R / 698 D**, up from 146 R. These are recovered text records, not estimates of
national ad volume, unique creative executions or audience exposure.

The newly registered Club for Growth public WordPress archive supplies **six Republican
records from five releases**, dated March 25-September 9: three House records
(AK-at-large, AZ-05 and FL-19) and three Senate records (two AL, one NE). All 93
in-window posts returned by its ad search were checked. Three records are explicitly
marked full scripts; three contain only explicitly attributed ad quotations and retain
the `publisher_ad_copy_completeness_unverified` flag. Separate excerpts from the same
AZ-05 ad form one partial record. The two AL ads remain separate records, each linked
to its own original video through the named candidate in the publisher's watch link;
their praise and criticism are not combined into a fabricated contrast ad.

Attribution follows each release's named organization: one Club for Growth Action,
three Win It Back PAC and two Alabama Freedom Fund records. These affiliates are not
interchangeable legal payers; sole payer identity is not independently verified.
Appended news excerpts are excluded from marked scripts. Governor/state-only material,
spokesperson statements, polling, spending announcements without ad text and ambiguous
multi-video quotations are not admitted. Exact reviewed Senate aliases for Barry Moore
and Steve Marshall are corroborated by their FEC principal committees, not surname-only
or fuzzy matching. Recognized and publisher-quoted text is not rewritten.

All **1,824 preceding acquired ad objects remain field-for-field unchanged**. The six
additions have six new exact normalized message identities and remain explicitly
unreviewed for semantic portrayals; unreviewed is not neutral. Selected cache-only
collection reproduces the new partition. Complete exports, Parquet, eleven PNG figures,
the technical report and both unpublished editions are rebuilt together.

**The large Republican House gap remains unresolved.** AFL-CIO and Working America
supply 491 Democratic records across all chambers, including 355 House records.
Additional public ad galleries exposed video
links rather than usable scripts; the publisher's 31 in-window PDFs were polling,
policy, organizational or legal material, not additional verified federal ad scripts.
The new source is included in ordinary research-only refreshes, but this bounded
follow-up does not exhaust accessible national sources or establish party ad prevalence.
Existing access denials remain paused, and no website/Substack publication occurred.

### House platform-mix diagnosis

Before the three-record recovery above, the House gap depended strongly on the
acquired platform mix:

| English House text records | Democratic-aligned | Republican-aligned |
|---|---:|---:|
| All acquired sources | 698 | 149 |
| Snap sources | 476 | 1 |
| Sources other than Snap | 222 | 148 |

Reproduce this table from `outputs/analysis.json` at `dataset.ads`: select
`chamber == "House"` and alignment `D` or `R`, then classify Snap records by
`source.endswith("-snap")`. This is a collection diagnostic, not a new exclusion
rule: no records are removed. Neither the full nor the non-Snap subset estimates
national party ad volume. The non-Snap comparison is still unmatched by publisher,
race, format and date. The 149 Republican records are not an acquisition ceiling.

Further first-party discovery found five House video links in Driving Force
Action's [September release](https://drivingforceaction.org/2026/09/23/driving-force-action-launches-six-figure-ad-buy-in-battleground-states/)
and [October follow-up](https://drivingforceaction.org/2026/10/20/driving-force-action-launches-six-figure-ad-buy-in-battleground-states-2/):

| Supported candidate | Race | Publisher-linked YouTube IDs |
|---|---|---|
| Tom Barrett, FEC H2MI07123 | MI-07 | `nTbaSiApwMk`, `k1AdPSx5vXU` |
| Ryan Mackenzie, FEC H8PA15195 | PA-07 | `byGYL96smGA` |
| Derrick Van Orden, FEC H0WI03175 | WI-03 | `vWbuCYjt4WQ`, `4xgFtbkcAN0` |

These are five linked videos, not five newly recovered texts or independently
verified unique creatives. No release summary or link title is counted as spoken
ad copy. The October page path says October 20 while its release PDF says October
21; neither establishes first paid delivery. Candidate joins use the existing
exact reviewed public-name aliases where needed, not surname-only matching.

The publisher's public WordPress video inventory exposed one separate July-uploaded,
15-second original. Local speech recognition recovered no speech; inspected frames
show general voter-mobilization imagery without a named federal candidate. It is
not substituted for the five linked House videos. Its original SHA-256 is
`747a7030cdca1da392a77b3ba080da5c18bdd9d5b50ef377dcb301890ad4c3af`.
Native video OCR failed; locally decoded frames were inspected instead. The five
House leads still need permitted original media or actual transcripts. Existing
provider denials were not retried. Discovery and text recovery remain separate;
these results do not establish that available Republican House ads are exhausted.

## Earlier October 30 Republican-coverage recovery

The preceding snapshot contained **1,824 acquired text records**, including **1,786 English
records: 1,226 Democratic-aligned, 521 Republican-aligned, 31 other and eight unresolved**.
The exact party/message counts are **1,204 D / 484 R**. Neither measure certifies distinct
creative executions or nationally representative advertising volume.

This recovery adds **24 Republican English records and 24 exact normalized messages** over
the preceding snapshot's 497 R records / 460 R messages, without dropping Democratic records:

- The fresh official October 30 Snap archive supplies eight Senate Leadership Fund creatives
  and two Ken Paxton creatives. Every currently matched Republican Snap lead now has acquired
  text; this does not cover unmatched advertisers or other platforms. Two short English image
  texts needed individually reviewed, exact-source-hash-bound language overrides; original
  automatic labels remain in the evidence.
- The newly registered Cassidy campaign archive supplies eight January 27-May 4 Senate scripts.
  Its 207-page public blog sitemap was checked against actual publication metadata and visible
  article bodies. Whitespace in one JSON-LD headline had defeated the exact visible-heading
  check; normalization fixes that without accepting genuinely mismatched titles. Seven scripts
  are campaign releases; one explicitly NRSC-produced/released script is attributed to NRSC,
  not automatically to the hosting campaign. Its sole legal payer is not independently verified.
- Six May 27-September 20 Husted campaign-linked originals were recovered with local speech
  recognition and frame OCR. The public widget exposed 109 post cards spanning May 13-October 30;
  that is not complete account discovery. All six full extractions and actual closing payer
  cards were reviewed: two Husted for Senate, one NRSC-paid/candidate-authorized, and three
  Husted Victory joint-fundraising ads. FEC C00937797, designation J, corroborates the latter
  identity. Exact post timestamps, public continuation forms, original-byte SHA-256, literal
  evidence and extraction caveats are saved in `data/campaign-native-reviews.json` and the
  canonical records. A separately recovered news clip was rejected, not counted as an ad.

All **1,800 preceding acquired ad objects remain field-for-field unchanged**. Newly acquired
messages are explicitly unreviewed for semantic portrayals; old saved judgments are not
silently extended to them, and unreviewed does not mean neutral. Complete evidence downloads,
PNG figures, the technical report and both unpublished editions are rebuilt from the same
inputs. `political-ads build`, `political-ads validate` and `political-ads audit-strategy`
reproduce and check the saved analysis without fetching sources or invoking a model.

**At that checkpoint,** English House records were **146 R / 698 D**;
all 24 additions above are Senate material. AFL-CIO and Working America alone supply **491
of the 1,226 D records**, so the overall imbalance is materially source-dependent. A bounded
House follow-up checked reachable campaign media pages and further source leads but recovered
no additional qualifying House text. Unverified candidate-domain guesses were not treated as
official campaign sites; video embeds, ordinary news/speeches and a CLF page explicitly labeled
2024 were not counted as current-cycle ads. Meta authorization is still unconfigured, while
previously denied Google/YouTube and other sources remain paused. These are acquisition
limitations, not evidence that Republicans advertise less, nor a claim that accessible national
collection is exhausted. The dated acquisition notes below describe earlier checkpoints.

| Source | Working path | Text / limits |
|---|---|---|
| NRSC | Public WordPress posts, broader ad search | 58 written Republican Senate records; explicit body-announced ads need not say ad in the headline |
| DCCC | Public WordPress posts, transcript search | Democratic House transcripts; creatives separated; Spanish text excluded from analysis |
| DSCC | Public `article` REST type, ACF body, ad search | Five explicit scripts; four recovered by expanded heading recognition |
| Roy Cooper | Official public WordPress posts | Italic transcript paragraphs; NC Senate candidate |
| Ashley Hinson | Official public WordPress ad releases | Separately quoted ad copy; IA Senate; completeness flagged |
| Bill Cassidy | Public blog sitemap, publication metadata and exact article body | Eight January-May Senate scripts; seven campaign releases and one NRSC-produced mirror with explicit payer uncertainty; 207 sitemap pages checked |
| Jon Husted | Individually reviewed originals exposed by the campaign's public feed and actual load-more form | Six Senate ads; two candidate-paid, one NRSC-paid and three Husted Victory joint-fundraising; exact post dates and original hashes; machine extraction errors preserved |
| Dan Sullivan | Official public WordPress ad releases | Six explicit transcripts; AK Senate; own-ad ICYMI release retained separately from ordinary news |
| John Hickenlooper | Official public WordPress ad releases | Explicit transcripts; CO Senate |
| Jon Ossoff | Official public WordPress ad releases | Radio scripts and bracketed-speaker ad copy; GA Senate |
| Mike Rogers | Paginated public Squarespace news JSON | Fifteen written scripts; MI Senate |
| Josh Turek | Rendered first-party news index and release pages | Thirteen written scripts; IA Senate |
| Troy Jackson | Dated public news cards and official release pages | Eleven written scripts; ME Senate; visible archive is partial |
| Abdul El-Sayed | Paginated dated public news cards and official releases | Twenty-four scripts/copy records; MI Senate; API authorization is not bypassed |
| Mike Collins | Public `press_release` WordPress type | Two written scripts; GA Senate; ordinary posts endpoint is empty |
| Andy Barr | Public WordPress ad releases | Eight explicit full-text scripts, February through October; KY Senate; unlabeled release background excluded |
| Susan Collins | Public WordPress ad releases | One explicit July script; ME Senate; release descriptions and spokesperson quotes are not scripts |
| Michael Whatley | Public WordPress ad releases | NC Senate; 48 matching posts checked; video/description leads, no usable written scripts |
| Pete Ricketts | Public WordPress ad releases | NE Senate; one matching ordinary post checked; no usable written script, not proof of no ads |
| Young Kim | Public WordPress ad releases | Two April primary scripts; CA-40 verified against release and FEC roster; horizontal divider excludes next-ad commentary |
| Mike Lawler | Official public WordPress releases | Five publisher-quoted ad-copy records from four releases; NY-17; partial passages, not certified complete scripts |
| Maria Elvira Salazar | Official public WordPress releases | Two publisher-quoted ad-copy records; FL-27; ordinary press statements excluded and CMS/visible-release date disagreement retained |
| Juan Ciscomani | Paginated public Squarespace news JSON | One June script; AZ-06 |
| Roger Marshall | Dated public HTML press cards and release pages | Two October scripts; KS Senate; marked transcript paragraphs exclude surrounding attacks; visible archive is partial |
| Lizzie Fletcher | Official public WordPress ad releases | Four scripts, including separately marked 15/30-second versions; TX-07 |
| Zach Dembo | Official public WordPress ad releases | One written script; KY-06 |
| Nancy Lacore | Paginated public Squarespace `/media` JSON | Six scripts; SC-01; campaign biography excluded |
| Julia Letlow | Public blog sitemap, publication metadata and exact article body | One June Senate script; sitemap modification dates and recent-post navigation are not ad evidence |
| Glenn Grothman campaign | Reviewed public campaign release reproduced by WisPolitics | One October WI-06 script; campaign alignment is not the mirror's editorial alignment; private API/feed access not used; mirror coverage is explicitly partial |
| Aaron Flint | Official public WordPress ad releases | Seven August–October MT-01 scripts; original speaker labels and publisher errors retained |
| Brian Stover | Official public WordPress ad releases | Two January GA-14 releases reproduce an ad script; post-script biography and placement commentary excluded; releases are not evidence of two distinct creatives |
| Eric Conroy | Official public WordPress ad releases | Two September OH-01 scripts; candidate identity verified against FEC H6OH01138; release descriptions excluded |
| Rob Bresnahan | Individually reviewed original videos linked by the campaign's public Facebook-feed widget | Ten PA-08 ads; exact publisher post timestamps, original-byte SHA-256, approval/payer evidence and actual FEC identity; local speech/frame OCR; dates are publisher posts, not verified first release or delivery |
| Brandon Herrera | Individually reviewed original video linked by the official campaign homepage | Full local speech/frame OCR preserved in the media backlog; no verified release/delivery date, so excluded from the dated corpus; filename and storage timestamps are not release evidence |
| Winning For Women | Official public WordPress advocacy release | One July TX-15 sample script supporting Monica De La Cruz; seven announced districts do not imply seven recovered scripts |
| WFW Action Fund | Official public WordPress ad releases | Six February-July House primary scripts: Steinmann, Mealer (two), Honeycutt, Pridemore and McKinney; separate PAC identity from Winning For Women |
| Club for Growth public archive | Public WordPress ad search; named affiliate announcements and actual federal-candidate evidence | Six records from five releases: three full scripts and three flagged partial ad quotations; three House and three Senate; CFGA, Win It Back PAC and Alabama Freedom Fund separately attributed; appended news and state races excluded |
| Sarah Trone Garriott | Official public WordPress ad releases | Explicit transcripts; IA-03 |
| Sean McCann | Official public WordPress ad releases | Explicit transcripts and separated ad copy; MI-04 |
| Zach Nunn | Official public WordPress ad releases | IA-03 video leads; releases without transcripts are not counted as text |
| SLF | Paginated public WordPress ad releases | Linked video captions acquired; bounded collection and caption quality flags; broader ad search checked 326 releases without recovering additional written scripts |
| HMP | Paginated public HTML news archive | Backfills beyond the custom REST endpoint's ten recent posts; caption acquisition remains partial |
| House Majority Forward | Paginated public HTML news archive | Thirteen English scripts; two Spanish scripts retained outside analysis; policy advocacy, not verified delivery |
| Unrig Our Economy | Public `news` WordPress type | Twenty English-classified scripts; five Spanish scripts retained outside analysis; issue advocacy |
| NRCC | Public full-text RSS plus reviewed native graphics | Complete accessible script-search feed checked: 97 releases, 69 written records; 16 reviewed standalone static ads; video thumbnails excluded; REST access is not bypassed |
| CLF | Paginated public HTML press archive | Actual next-page URLs followed through the 2025 boundary; two matching 2026 releases are spending reservations, not scripts; REST authorization is not bypassed |
| SMP / WinSenate | Public news cards and their shipped load-more form; native Snap assets | 37 in-scope ad releases checked; 10 explicitly quoted speech records, not full certified scripts; ordinary posts endpoint misses this archive; WinSenate is FEC C00865444 |
| One Nation | Official public advocacy identity and native Snap assets | Conservative-aligned issue advocacy, not a party committee; FEC noncommittee disclosure ID retained separately; federal-candidate names or individually reviewed, hash-bound federal-identity evidence required |
| Working America | Reviewed official advocacy identity and native Snap assets | Organizational identity and alignment reviewed separately; each creative needs recovered 2026 federal-candidate evidence; generic and state-only material excluded |
| Affordable Pennsylvania | Original Snap images and primary organizational/House identity evidence | Two complete PA federal-advocacy graphics; exact image/source-hash-bound surname and Washington phone-number reviews; CFFE project alignment is distinct from legal payer identity |
| UA Vote! PAC | Public `news` REST type and ACF release bodies | Four explicitly marked federal scripts; Iowa governor script excluded; reviewed bipartisan publisher is other, including its pro-Republican Fitzpatrick ad; original unknown acquisition labels remain in provenance |
| VoteVets | Public post metadata plus exact release-body HTML | Thirteen federal scripts recovered despite empty API bodies; state races and video-only pages excluded; Democratic organizational alignment does not identify a sole PAC/fund payer |
| Other reviewed native payers | Official organizations, exact FEC identities and reviewed landing-page disclosures | Campaigns, PACs, unions and advocacy entities remain distinct; unresolved alignments stay in the corpus but not D/R denominators; metadata-only leads are not analyzed ads |
| FEC | Official 2026 candidate/committee bulk ZIPs | Identity/discovery metadata, not transcripts or one-to-one creative links |
| LCV Victory Fund | Public sitemap and rendered archive/release HTML | Explicit publisher scripts recovered; inaccessible REST does not imply the separate public HTML is unavailable |
| RJC Victory Fund | Public WordPress releases | Three identifiable video leads; metadata is not text |
| Protect Freedom PAC | Public dated federal-ad gallery | Fourteen federal video leads; state/out-of-window material excluded |
| Club for Growth Action | Public ad gallery | Twenty-two video leads; dates unverified, not analyzed scripts |
| Google | Official ZIP, public native creative viewer, local OCR | 19,682 federal leads by exact public FEC IDs; 76 native preview text records recovered before HTTP 429; VIDEO metadata is not a transcript |
| Snap | Official 2026 archive and original image/video assets | Exact federal identity joins plus reviewed advocacy payers; the latter require federal-candidate evidence in recovered text; local OCR/ASR; inventory candidates are not all analyzed ads; scheduled dates are not verified daily delivery |
| Meta | Ad Library API | Free identity/developer authorization required; not configured, no acquired-text claim |
| X | Official disclosure documentation/archive links checked | Linked ZIP returns 404; another official host returns 403; CDN response is HTML, not a ZIP; no text acquired |
| Roku | Official political-ad-archive page and its linked public SharePoint folder | Folder returned 403; no text acquired and no access-control workaround attempted |
| Reddit | Official 2026 election-policy announcement, linked advertising policy and public political-ad community | Linked policy returned 404; community page did not expose usable ad text; no acquisition claim |

Official entry points and explicitly identified release mirror:

- https://www.nrsc.org/
- https://dccc.org/
- https://www.dscc.org/
- https://roycooper.com/
- https://ashleyhinson.com/
- https://www.billcassidy.com/
- https://www.jonhustedforsenate.com/
- https://dansullivanforalaska.com/
- https://hickenlooper.com/
- https://electjon.com/
- https://rogersforsenate.com/
- https://turek4iowa.com/
- https://www.jacksonformaine.com/news/
- https://abdulforsenate.com/news/
- https://mikecollinsga.com/
- https://barrforsenate.com/
- https://susancollins.com/
- https://michaelwhatley.com/
- https://www.petericketts.com/
- https://youngkimforcongress.com/
- https://www.lawlerforcongress.com/
- https://mariaelvirasalazar.com/
- https://juanciscomani.com/
- https://www.kansansformarshall.com/news
- https://www.lizziefletcher.com/
- https://zachdembo.com/
- https://www.nancylacore.com/media
- https://www.julialetlow.com/press-statements
- https://www.wispolitics.com/2026/u-s-rep-grothman-releases-first-campaign-ad-of-2026-cycle/
- https://flintformontana.com/
- https://www.brianstoverforcongress.com/
- https://winningforwomen.com/
- https://www.wfwactionfund.com/
- https://ericconroy.com/
- https://sarahforiowa.com/
- https://seanmccannforcongress.com/
- https://zachnunn.com/
- https://senateleadershipfund.org/
- https://www.thehousemajoritypac.com/
- https://www.housemajorityforward.org/news
- https://unrigoureconomy.com/news/
- https://www.nrcc.org/
- https://congressionalleadershipfund.org/
- https://www.senatemajority.com/
- https://www.fec.gov/data/committee/C00865444/
- https://www.onenationamerica.org/
- https://workingamerica.org/
- https://www.uagetinvolved.org/
- https://votevets.org/
- https://www.lcvvictoryfund.org/
- https://www.rjchq.org/
- https://www.protectfreedompac.com/
- https://www.clubforgrowthaction.com/
- https://www.fec.gov/data/browse-data/
- https://storage.googleapis.com/political-csv/google-political-ads-transparency-bundle.zip
- https://www.facebook.com/ads/library/api/
- https://www.snap.com/political-ads/
- https://help.x.com/en/business-and-advertising/political-ads-disclosure
- https://advertising.roku.com/roku-s-political-ad-archive
- https://redditinc.com/news/supporting-civic-knowledge-and-participation-for-the-2026-us-elections

Retrieval declares a research user agent and uses public endpoints. Unauthorized responses
are not bypassed or retried as transient failures. Network/rate errors have bounded retries.
Failures retain prior text and last-success dates. Media attempts are checkpointed; metadata-only
records never become analyzed ads.

The expansion also checked additional Senate and House campaign sites and broader DCCC/NRSC
ad searches. Empty endpoints, unauthorized responses, and releases containing only commentary
did not produce counted ads. HMP's 2026 archive exposed 183 distinct public video links;
these are acquisition leads, not 183 additional analyzed texts. Caption-service rate limits
stop the entire run, preserving recovered text for subsequent scheduled collection.
Three short opponent-speech clips linked from an NRCC ad-rebuttal post were excluded after
review: linking a clip while criticizing an opponent's ad does not make it the publisher's ad.

The current local corpus combines written publisher scripts/quoted ad copy, saved public captions,
reviewed native graphics, Google native previews and Snap native image/video text. Exact totals,
party denominators, distinct exact-message counts, publisher composition and monthly tables are
generated together in `outputs/analysis.json` and `outputs/analysis.html`; the matching
`outputs/analysis-ads.csv` includes complete text and evidence. These files, not an earlier
379-record checkpoint, define the current reconciled local snapshot.

The reconciled October 27 cutoff contains 1,789 acquired text records: 468 written records,
65 captions, ten reviewed campaign-original videos, 16 static graphics, 76 Google previews
and 1,154 Snap creatives. The English explorer contains 1,751 records:
**1,216 Democratic-aligned, 496 Republican-aligned,
31 reviewed bipartisan and eight unresolved**. Only D/R enter party comparisons.
The October 27 publisher-alignment audit corrected the earlier
758 D / 440 R / 478 unresolved classification to **1,194 Democratic-aligned, 443 Republican-aligned,
31 reviewed bipartisan and eight unresolved**, before this new acquisition.
That audit added no ads or text: of the former 478 unresolved records, 436 are now D-aligned,
three R-aligned, 31 bipartisan and eight still unresolved. The separate acquisition expansion
from the 949-record checkpoint added 17 Republican written records. Three previously unassigned
Cornhusker Majority Snap records are now R-aligned; that is reclassification, not new acquisition.
Record counts are not counts of distinct creative executions.
All 1,606 matched Snap native leads were attempted; 362 still lack sufficient federal identity and
90 have no substantive recovered text. These exclusions are not analyzed ads.

The subsequent October 27 acquisition recovers **32 additional Republican English records**:
25 NRSC, two Mike Rogers, two Dan Sullivan, one Aaron Flint and two Eric Conroy.
A headline-only gate had rejected explicitly announced ads with marked scripts; reviewed
named-producer body announcements now admit those releases, and standalone transcript-dash
headings are recognized. Legislative/news transcripts, interviews, speeches and ordinary
campaign videos remain excluded. Each new recovered script was read in full.
Multi-ad announcements can reproduce individually released scripts; neither new release records
nor exact normalized text identities certify distinct creative executions or paid delivery.

All 1,714 prior record IDs remain. Recollection also applies the existing background-boundary
rule to `nrsc-15447-0`, removing release commentary after its marked script without rewriting
spoken text. One refreshed NRCC release has a new raw-body hash but unchanged recovered text.
Native extraction bytes, alignment-review bindings, candidate reviews and language reviews
remain unchanged. Complete local and built JSON/gzip/CSV exports reconcile field by field;
all 1,789 Parquet rows match the loaded corpus.

The House-focused follow-up adds **seven Republican English script records**, raising
Republican English House coverage from 129 to **136**. Winning For Women supplies one
July housing-advocacy sample supporting Monica De La Cruz (TX-15). Its separately identified
WFW Action Fund supplies six primary scripts: Jessica Steinmann (TX-08), two Alex Mealer
ads (TX-09), Jenny Costa Honeycutt (SC-01), Tricia Pridemore (GA-11), and Amanda McKinney
(WA-04). Scripts span February-July. The two organizations' three and 32 matching releases
were checked, respectively. All seven scripts were read in full, with ordinary statements,
fundraising boilerplate and next-creative headings excluded. The seven-district advocacy
announcement contains one sample, not seven independently recovered variants.
Exact campaign/FEC evidence supports two additional name aliases, Alex Mealer and the
full Jenny Costa Honeycutt name; there are now 30 reviewed aliases, not fuzzy matches.
At that House-recovery checkpoint, all 1,746 prior acquired records remained field-for-field unchanged.

The October 27 research refresh adds **16 script records: 14 D-aligned
and two R-aligned**. These comprise seven DCCC scripts, three Nancy Lacore scripts, two
Sean McCann scripts, two Josh Turek scripts, one NRSC script and one Mike Rogers script.
All were read in full. Some are newly indexed earlier releases, not October 27 ad debuts.
All 1,753 prior records remain with unchanged text and segments; refreshed body hashes,
observation dates and public media links account for prior-record metadata changes.
Native extraction bytes and bound reviews remain unchanged. Grothman's mirror returned 403;
its saved script and October 26 last-success date are preserved, and later automated runs
pause that source without new requests. Republican English House coverage remains 136.
The daily workflow collects public release text, rebuilds complete analysis/downloads and
pushes only to this research repository. The website integration remains removed.

The first hosted refresh, run `40568363571`, passed all 156 Python, five frontend and four
browser tests and committed the validated evidence as Hans Hanley. It added no records
beyond the 16-script local refresh; all 1,769 records retained their text and segments.
Two Marshall release-body hashes changed without changing recovered text. RJC's public
archive returned 403 and is paused for subsequent runs; Letlow's publication-metadata
check failed, so its existing script was retained rather than replaced or dropped.

The next native acquisition adds **12 dated text records: four R-aligned and eight
D-aligned**, with all 1,769 prior ad objects retained field-for-field unchanged.
Republican English House coverage rises to **138**. The four Republican additions are
two Senate creatives from SLF and One Nation and two original Bresnahan PA-08 videos.
The campaign's own public homepage links the original video files and exact post IDs/times:
October 23 and October 25. Approval/payer evidence and FEC H4PA08124 establish the ad and
candidate identity. These are publisher-post dates, not certified initial air dates or paid
delivery. Speech and frame OCR retain their original errors, including potentially significant
name/negation errors in automatic transcription, with explicit quality flags.
The five separately dated Bresnahan release pages expose video embeds but no usable scripts;
their descriptions and spokesperson prose are not counted as recovered ad copy.

An additional original Herrera TX-23 video, linked in the campaign's own homepage code,
has 57 recovered text segments preserved in `outputs/media-backlog.json` with the exact
original-byte hash and FEC H4TX23120 identity. Its filename, storage modification and
homepage dates do not verify its release, so it remains outside dated counts and comparisons.
The replayable `campaign-native` collector requires the individually reviewed publisher
link/post timestamp, original media hash, actual candidate and recovered quotations.
It preserves prior acquisitions, keeps undated text separate and persists access-denial pauses.

Following the campaign homepage's actual public **Load more** control recovered eight more
reviewed Bresnahan PA-08 ad originals. Forty ordinary public-feed pages expose 239 posts,
reaching December 1, 2025. Of 47 video-marked 2026 posts, 46 expose original links: two
were already acquired, and 44 additional originals were recovered for review. The remaining
January 16 card has an empty original-video field, no video/source/iframe tag and a public
player fallback to Facebook; its caption and thumbnail are not substituted for ad text.
The eight accepted 30-second ads have publisher-post dates August 5, August 10, September 9,
September 18, September 28, October 1, October 5 and October 13. Each recovered script was
read in full and its actual closing payer card inspected. The August 5 execution is paid
for by **NRCC**, authorized by Rob for PA; it is not candidate-paid. The other seven
identify Rob for PA as payer. These additions raise Republican English House coverage
from 138 to **146**, but add no new candidate or district.

The other 36 newly recovered originals remain outside the analyzed ad count: ordinary
remarks, interviews, news/opponent excerpts and event footage are not automatically ads,
and several social montages lack sufficient execution/payer evidence. Exact media hashes,
post IDs/timestamps and recovered-quote gates bind the eight accepted reviews. Replaying a
paginated record requires the homepage's exposed same-origin read-only public feed form;
both the homepage and actual paginated-body hashes are retained. The embedded Graph URL
contains only the plugin's public placeholder, not an API credential, and is sent only to
the campaign's own public handler, never directly to Graph. No denied provider was retried
or bypassed. All 1,781 prior ad objects remain field-for-field unchanged. These are bounded
publisher-specific results, not national exhaustion or 44 newly verified ads.

The fresh official Snap ZIP has SHA-256
`5b2d96aca5794a5755157c5f162836a934de5cc4d067b970877c5e21684e1121`,
11,245 rows and an October 27 21:11:27 GMT modification time. Exact reviewed mappings
yield 1,606 candidate creatives across 2,749 platform records; 1,154 have usable federal
text and 452 remain excluded. All raw Republican-mapped leads have extracted text.
The unmatched inventory still has 215 payers and 2,915 creatives; these are leads, not
recovered ads. Five additional unmatched landing sites were investigated; governor/state
legislature/charity material was not converted into federal ad text.

Two newly recovered Affordable Pennsylvania images identify Representatives Mackenzie
and Perry by surname, PA context and their exact Washington office numbers. Both complete
original images were visually inspected; the official House directory independently confirms
the numbers and identities. Two narrowly hash-bound reviews bring the federal-scope ledger
to 29 entries without weakening full-name matching globally. OCR is unchanged, including
the bullet in Perry's phone number. The publisher explicitly identifies itself as a CFFE
project; a separate exact-record organizational-alignment review uses that primary relationship
and the existing 2026 CFFE electoral-program/FEC audit, preserving independent-support
exceptions and not assigning another entity's PAC ID as this project's legal payer.
Selected offline replay is available with repeatable `snap-collect --ad-id` flags, so a new
review need not replay or change previously acquired native records.

The wider Republican House pass checked 15 cached campaign homepages from a 25-entry-point
inventory and completed a separate twelve-campaign live probe. It did not find another
usable direct original in those bounded checks. DNS failures, timeouts, missing cache entries
and video-only embeds are not proof that those campaigns did not advertise.

The same investigation corrected CLF pagination: its next link uses `page-link`, not `next`.
Following the actual same-publisher next URL reaches the 2025 boundary, but recovers only
two 2026 spending-reservation releases, neither counted as ad text. A wider NRCC RSS union
contains 129 releases; all 17 distinct images among 30 additional image-record leads were
visually inspected and rejected as video thumbnails. Nunn's 16 matching posts, Noveletsky's
11, Beltran's seven (including four actual ad pages), nine current AAN ad releases and
AFP Action's 141 matching posts yielded no additional written scripts. Harding's accessible
news JSON and original news lead were checked; raw advertising B-roll is not an ad.
Other PAC galleries, campaign pages and unmatched native payer identities were also checked.
These are source-specific outcomes, not an exhaustion claim or proof that no ads exist.
No blocked caption/creative endpoint was retried, no access control bypassed, and no new
native extraction or published website update is claimed.

Additional public probes checked Wesley Hunt (19 matching posts), Ashley Moody (30),
Cindy Hyde-Smith (zero ordinary matching posts), Brian Fitzpatrick (six) and SLF's broader
326-release search without recovering written scripts. These are query-specific findings,
not evidence that the candidates did not advertise. Eight registered Republican archives and
the broader SLF results exposed no independent usable audio/video/caption mirror in the
reviewed release bodies; linked legislative/background PDFs are not scripts. Two SLF releases
link the same Dropbox clip as evidence for an opponent's remarks, not as the advertised creative.
RNC's own public ad-transcript search returned no results. These discovery attempts and
metadata-only leads are not added to analyzed-ad totals. Republican House and early-cycle
coverage remain incomplete; this checkpoint is not a claim of exhaustive collection.

Non-English and uncertain-language records remain in acquisition partitions outside the English
comparison. Forty-six clear English recovered texts received
contextual language adjudication, bound to exact source hashes in `data/snap-language-reviews.json`.
Original automatic labels remain in segment evidence. This review does not certify OCR accuracy
or the political claims. Other uncertain records are not automatically relabeled English.
Four Alliance for Youth Power videos with doubtful or repetitive recognized speech remain
outside the English analysis rather than receiving language overrides on their readable overlays.

The native discovery output also retains a safe unmatched-payer review inventory with public
payer names, asset links, platform IDs, reported FEC IDs, landing hostnames and candidate-ballot
descriptions. It omits billing addresses, targeting data and tracking query strings. Unmatched
does not mean out of scope or exhausted. A reviewed identity that fails its landing-host or
committee constraints remains visibly unresolved rather than silently merged.

Reviewed mappings distinguish parent unions from their political funds, registered PACs from
noncommittee disclosure filers, and similarly named organizations. United Association's own
description is explicitly bipartisan; labor affiliation is not a blanket Democratic label.
`data/publisher-alignments.json` retains all 23 sponsor/source reviews, primary evidence,
qualitative 2026 FEC filing observations and exact acquisition hashes for 496 records, of which
478 are English-eligible. These derived reviews do not change the acquisition partitions,
candidate/language review hashes, payer IDs or recognized text.

The AFL-CIO grouping is Democratic-leaning, not exclusively Democratic: its own linked 2026
endorsement table has 322 distinct federal name/state/office entries. Of 257 exact FEC joins,
244 are DEM, five DFL, four REP and four IND; 65 names remain unjoined rather than guessed.
Current national electoral-program evidence supports the grouping, while Republican and
independent endorsements remain explicit exceptions. AFSCME's own identification of PEOPLE
as its political program and that exact fund's current federal filings support both AFSCME
publisher groupings without transferring the fund's ID to the parent payer.

Current FEC general-election support/oppose disclosures independently substantiate the other
reviewed PAC groupings. The LCV and CFFE/Opportunity Action Fund parent-program relationships
are documented by their own websites; program IDs are evidence references, not substituted
creative-payer identities. Lower Costs Now and CFFE also support independents; CFFE's
Democratic-opposition exception is retained. The filings are not summed as spending, counted
as ads, or joined one-to-one to creatives. Late reports for earlier elections are excluded.

The eight unresolved English records are four from Midnight Sun Independence Fund, two from
DemsVote and two from Fair Deal Alaska. The first lacks a verified organizational program
identity; the second lacks substantiating current-cycle evidence beyond its payer/committee name;
the third's available primary interventions do not establish party alignment. Empty FEC queries
do not establish absence of activity or funding. These are reviewed uncertainties, not missing
transcripts. UA's 31 cross-party program records are separately filterable as other, not unknown.

The 2026 Texas Forever committee (C00962308) is not an older similarly named committee.
For Michigan Action Fund (C00886093) remains separate from the For Michigan parent organization,
whose mapping additionally requires the exact `4mich.org` landing host. Fair Deal Alaska
(C00957555) is separately identified. Raw identity mappings retain their original labels;
the independent alignment review assigns Texas Forever and For Michigan Action Fund to D
from their own current general-election filings. Fair Deal Alaska remains unresolved.
Committee identity, landing-page attacks or support for an individual primary candidate do not
by themselves establish organizational party alignment. Each native creative still requires
recovered federal-candidate evidence before entering the text corpus.

SAM Project Action Fund's exact archive payer name is corroborated by the visually reviewed
`SAM-PROJECT.ORG` disclaimer in its public native creative and the public SAM Project website.
The fund name is retained without asserting legal equivalence to the website's organization,
assigning a PAC ID or inferring party alignment from a progressive mission. Presidential
criticism or generic November turnout alone does not meet the House/Senate scope gate.
All 59 initially rejected creatives from the five newest payer mappings were read in full.
Exact public-name aliases for Ken Paxton, Will Lawrence and Tom Barrett recover formal-name
misses without changing the FEC roster or recognized text. State-only, generic turnout and
insufficient-identity material remain excluded; payer identity alone does not establish scope.
An additional Paxton creative received a hash-bound identity review after direct inspection of
its original opening frame, which explicitly names KEN PAXTON. Its recognized spelling Paxson
is retained unchanged; this does not authorize approximate matching in other creatives.

The two new written archives require actual 2026 federal-candidate identity evidence in the
ad or its release heading, not a candidate mentioned only in surrounding press commentary.
VoteVets's empty API bodies are not empty public releases: extraction uses only the precise
public article-body container, never next-post navigation. Explicit background headings
terminate scripts even when a space precedes the colon. The original publisher's spelling
and transcription errors remain unchanged.
Unknown-alignment records remain available in the explorer and complete downloads. The
Majority Forward and Midnight Sun landing-page disclosure conflict is not resolved by assigning
one organization's identity or committee IDs to another.

### Locally reviewed temporal coverage

The generated monthly tables use the first observed release, Google-reported delivery start,
or Snap scheduled start of each exact message. Those date bases are not interchangeable or
verified daily airings. Publisher counts include saved records in the month, including mirrors
of previously observed messages. Snap placement intervals and positive reported impressions
do not establish the days on which exposure actually occurred.

March's NRCC releases repeat the same script across 22 releases, counted as one exact message.
April's larger count includes changed-target Tax Day templates, which remain separate messages.
These bursts and the changing publisher mix are collection/composition effects, not evidence of
national advertising volume or a shift in party strategy. Early Democratic coverage and
Republican House candidate coverage remain particularly sparse.

Further public probes checked Kean, Mackenzie, Bresnahan, Kiggans, Lawler, Gabe Evans, Cassidy,
Husted, Moody, and additional outside-group routes. Husted's public `press-releases` type exposed
20 matching releases but no explicit usable scripts; ordinary posts alone had missed this archive.
Unsupported page formats, missing routes, and access denials are not empty-advertising findings.
Hunt for Senate's public archive supplied 19 matching 2026 releases but no explicitly usable
written script. Letlow's full public blog sitemap supplied one script; its older dynamic-release
sitemap contained a non-ad announcement. Grothman's public mirrored release supplied an explicit
script despite unavailable API/feed routes. The mirror's UTC timestamp is converted to its
Central time zone, matching the visible October 15 release date; upcoming-event dates are ignored.
LCV Victory Fund's REST endpoint returned 401 and was not bypassed; separate public HTML supplied
explicit scripts. Blocked YouTube captions and Google creative requests are not retried.
Snap's independently available original videos are processed locally with multilingual Whisper
and timestamped Apple Vision frame OCR; media is not uploaded to hosted recognition services.

House Majority Forward describes itself as progressive and is House Majority PAC's sister
organization, not a formally registered Democratic Party committee. See its
[own description](https://www.housemajorityforward.org/about-hmf) and
[organizational reporting](https://punchbowl.news/article/house/house-majority-forward-evans-lawler/).
Unrig Our Economy is an issue-advocacy campaign, not a party committee. Its D-aligned grouping is
an editorial inference from its [coalition history](https://unrigoureconomy.com/about/) and
[published campaign strategy](https://unrigoureconomy.com/news/the-new-republic-biden-has-been-touting-the-middle-class-for-two-years-but-the-middle-class-may-not-be-listening/),
not a formal party registration or a label inferred from individual ad phrases.
Neither publisher identity establishes a creative's
sole payer or verified delivery. Source/sponsor filters keep these groups separate from campaigns.

Additional Republican-side probes checked One Nation's public ad releases and American Action
Network's public press archive. Written-release probes exposed video leads rather than usable
scripts; One Nation's separate native Snap route can supply actual recovered creative text.
An interactive phone-tree transcript linked
from an El-Sayed ad announcement was also excluded: it is not the 15-second ad's transcript.

Verified delivery, complete candidate discovery, comprehensive on-screen text, and broad
Republican House candidate coverage remain gaps. Commercial/Wesleyan current catalogs are not free fallback
dependencies. Public access is not a blanket redistribution license; ownership and attribution
remain with original publishers.
