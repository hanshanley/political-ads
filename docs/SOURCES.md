# Free-source capabilities

Verified October 26, 2026. Live acquisition status accompanies each snapshot.
This is a source-limited release collection, not a platform-wide census.

| Source | Working path | Text / limits |
|---|---|---|
| NRSC | Public WordPress posts, transcript search | Written Republican Senate ad transcripts |
| DCCC | Public WordPress posts, transcript search | Democratic House transcripts; creatives separated; Spanish text excluded from analysis |
| DSCC | Public `article` REST type, ACF body, ad search | Ordinary posts endpoint empty; one explicit transcript in pilot |
| Roy Cooper | Official public WordPress posts | Italic transcript paragraphs; NC Senate candidate |
| SLF | Paginated public WordPress ad releases | Linked video captions acquired; bounded collection and caption quality flags |
| HMP | Recent public release index | Custom endpoint ignores pagination/search; captioned recent releases, explicitly partial discovery |
| NRCC | Public RSS alternative | REST returns 401; RSS ad discovery works; captions may rate-limit |
| CLF | Public RSS/feed attempts | REST returns 401; query feed not parseable XML; no counted text from failed route |
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

Verified delivery, complete candidate discovery, comprehensive on-screen text, and broad
Republican House coverage remain gaps. Commercial/Wesleyan current catalogs are not free fallback
dependencies. Public access is not a blanket redistribution license; ownership and attribution
remain with original publishers.
