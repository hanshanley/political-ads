# Free-source capabilities

Verified October 26, 2026. Live acquisition status accompanies each snapshot.
This is a source-limited release collection, not a platform-wide census.

| Source | Working path | Text / limits |
|---|---|---|
| NRSC | Public WordPress posts, transcript search | Written Republican Senate ad transcripts |
| DCCC | Public WordPress posts, transcript search | Democratic House transcripts; creatives separated; Spanish text excluded from analysis |
| DSCC | Public `article` REST type, ACF body, ad search | Ordinary posts endpoint empty; one explicit transcript in pilot |
| Roy Cooper | Official public WordPress posts | Italic transcript paragraphs; NC Senate candidate |
| Ashley Hinson | Official public WordPress ad releases | Separately quoted ad copy; IA Senate; completeness flagged |
| Dan Sullivan | Official public WordPress ad releases | Explicit transcripts; AK Senate |
| John Hickenlooper | Official public WordPress ad releases | Explicit transcripts; CO Senate |
| Jon Ossoff | Official public WordPress ad releases | Radio scripts and bracketed-speaker ad copy; GA Senate |
| Mike Rogers | Paginated public Squarespace news JSON | Twelve written scripts; MI Senate |
| Josh Turek | Rendered first-party news index and release pages | Eleven written scripts; IA Senate |
| Sarah Trone Garriott | Official public WordPress ad releases | Explicit transcripts; IA-03 |
| Sean McCann | Official public WordPress ad releases | Explicit transcripts and separated ad copy; MI-04 |
| Zach Nunn | Official public WordPress ad releases | IA-03 video leads; releases without transcripts are not counted as text |
| SLF | Paginated public WordPress ad releases | Linked video captions acquired; bounded collection and caption quality flags |
| HMP | Paginated public HTML news archive | Backfills beyond the custom REST endpoint's ten recent posts; caption acquisition remains partial |
| NRCC | Paginated public full-text RSS | REST returns 401; written transcript and public captions recovered; captions may rate-limit |
| CLF | Paginated public HTML press archive | REST returns 401; public press archive checked; no usable 2026 scripts found there |
| SMP | Ordinary public posts endpoint | Empty response; no counted ad text, not evidence of no advertising |
| FEC | Official 2026 candidate/committee bulk ZIPs | Identity/discovery metadata, not transcripts or one-to-one creative links |
| Google | Public transparency ZIP | Reachable, about 313 MB; metadata alone excluded from analyzed ads |
| Meta | Ad Library API | Free identity/developer authorization required; not configured, no acquired-text claim |
| X | Official disclosure documentation | Lead only, not implemented; no acquired-text claim |

Official entry points:

- https://www.nrsc.org/
- https://dccc.org/
- https://www.dscc.org/
- https://roycooper.com/
- https://ashleyhinson.com/
- https://dansullivanforalaska.com/
- https://hickenlooper.com/
- https://electjon.com/
- https://rogersforsenate.com/
- https://turek4iowa.com/
- https://sarahforiowa.com/
- https://seanmccannforcongress.com/
- https://zachnunn.com/
- https://senateleadershipfund.org/
- https://www.thehousemajoritypac.com/
- https://www.nrcc.org/
- https://congressionalleadershipfund.org/
- https://www.senatemajority.com/
- https://www.fec.gov/data/browse-data/
- https://storage.googleapis.com/political-csv/google-political-ads-transparency-bundle.zip
- https://www.facebook.com/ads/library/api/
- https://help.x.com/en/business-and-advertising/political-ads-disclosure

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

The expanded saved snapshot contains 215 English records (120 Democratic-aligned and
95 Republican-aligned), up from 160: 152 written releases and 63 caption records. Some written
records are explicitly flagged publisher-quoted copy rather than verified complete transcripts.

Verified delivery, complete candidate discovery, comprehensive on-screen text, and broad
Republican House coverage remain gaps. Commercial/Wesleyan current catalogs are not free fallback
dependencies. Public access is not a blanket redistribution license; ownership and attribution
remain with original publishers.
