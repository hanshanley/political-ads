# Free-source capabilities

Verified October 26, 2026. Live acquisition status accompanies each snapshot.
This is a source-limited collection of releases and native platform creatives, not a census.

**Publication withdrawn:** the page, report, data downloads, preview, interactive-analysis card
and sitemap entry were removed and verified live. The host integration was removed, and the
automatic evidence-refresh workflow disabled. Expanded data remains local and must not be
pushed or published without explicit authorization.

| Source | Working path | Text / limits |
|---|---|---|
| NRSC | Public WordPress posts, broader ad search | Written Republican Senate ad transcripts; 1,242 matching releases checked |
| DCCC | Public WordPress posts, transcript search | Democratic House transcripts; creatives separated; Spanish text excluded from analysis |
| DSCC | Public `article` REST type, ACF body, ad search | Five explicit scripts; four recovered by expanded heading recognition |
| Roy Cooper | Official public WordPress posts | Italic transcript paragraphs; NC Senate candidate |
| Ashley Hinson | Official public WordPress ad releases | Separately quoted ad copy; IA Senate; completeness flagged |
| Dan Sullivan | Official public WordPress ad releases | Explicit transcripts; AK Senate |
| John Hickenlooper | Official public WordPress ad releases | Explicit transcripts; CO Senate |
| Jon Ossoff | Official public WordPress ad releases | Radio scripts and bracketed-speaker ad copy; GA Senate |
| Mike Rogers | Paginated public Squarespace news JSON | Twelve written scripts; MI Senate |
| Josh Turek | Rendered first-party news index and release pages | Eleven written scripts; IA Senate |
| Troy Jackson | Dated public news cards and official release pages | Eleven written scripts; ME Senate; visible archive is partial |
| Abdul El-Sayed | Paginated dated public news cards and official releases | Twenty-four scripts/copy records; MI Senate; API authorization is not bypassed |
| Mike Collins | Public `press_release` WordPress type | Two written scripts; GA Senate; ordinary posts endpoint is empty |
| Andy Barr | Public WordPress ad releases | Eight explicit full-text scripts, February through October; KY Senate; unlabeled release background excluded |
| Susan Collins | Public WordPress ad releases | One explicit July script; ME Senate; release descriptions and spokesperson quotes are not scripts |
| Michael Whatley | Public WordPress ad releases | NC Senate; 48 matching posts checked; video/description leads, no usable written scripts |
| Pete Ricketts | Public WordPress ad releases | NE Senate; one matching ordinary post checked; no usable written script, not proof of no ads |
| Young Kim | Public WordPress ad releases | Two April primary scripts; CA-40 verified against release and FEC roster; horizontal divider excludes next-ad commentary |
| Juan Ciscomani | Paginated public Squarespace news JSON | One June script; AZ-06 |
| Roger Marshall | Dated public HTML press cards and release pages | Two October scripts; KS Senate; marked transcript paragraphs exclude surrounding attacks; visible archive is partial |
| Lizzie Fletcher | Official public WordPress ad releases | Four scripts, including separately marked 15/30-second versions; TX-07 |
| Zach Dembo | Official public WordPress ad releases | One written script; KY-06 |
| Nancy Lacore | Paginated public Squarespace `/media` JSON | Three scripts; SC-01; campaign biography excluded |
| Sarah Trone Garriott | Official public WordPress ad releases | Explicit transcripts; IA-03 |
| Sean McCann | Official public WordPress ad releases | Explicit transcripts and separated ad copy; MI-04 |
| Zach Nunn | Official public WordPress ad releases | IA-03 video leads; releases without transcripts are not counted as text |
| SLF | Paginated public WordPress ad releases | Linked video captions acquired; bounded collection and caption quality flags |
| HMP | Paginated public HTML news archive | Backfills beyond the custom REST endpoint's ten recent posts; caption acquisition remains partial |
| House Majority Forward | Paginated public HTML news archive | Thirteen English scripts; two Spanish scripts retained outside analysis; policy advocacy, not verified delivery |
| Unrig Our Economy | Public `news` WordPress type | Twenty English-classified scripts; five Spanish scripts retained outside analysis; issue advocacy |
| NRCC | Public full-text RSS plus reviewed native graphics | 69 written records; 16 reviewed standalone static ads; video thumbnails excluded; REST access is not bypassed |
| CLF | Paginated public HTML press archive | REST returns 401; public press archive checked; no usable 2026 scripts found there |
| SMP / WinSenate | Public news cards and their shipped load-more form; native Snap assets | 37 in-scope ad releases checked; 10 explicitly quoted speech records, not full certified scripts; ordinary posts endpoint misses this archive; WinSenate is FEC C00865444 |
| One Nation | Official public advocacy identity and native Snap assets | Conservative-aligned issue advocacy, not a party committee; FEC noncommittee disclosure ID retained separately; federal-candidate names or individually reviewed, hash-bound federal-identity evidence required |
| FEC | Official 2026 candidate/committee bulk ZIPs | Identity/discovery metadata, not transcripts or one-to-one creative links |
| LCV Victory Fund | Public sitemap and rendered archive/release HTML | Explicit publisher scripts recovered; inaccessible REST does not imply the separate public HTML is unavailable |
| RJC Victory Fund | Public WordPress releases | Three identifiable video leads; metadata is not text |
| Protect Freedom PAC | Public dated federal-ad gallery | Fourteen federal video leads; state/out-of-window material excluded |
| Club for Growth Action | Public ad gallery | Twenty-two video leads; dates unverified, not analyzed scripts |
| Google | Official ZIP, public native creative viewer, local OCR | 19,682 federal leads by exact public FEC IDs; 76 native preview text records recovered before HTTP 429; VIDEO metadata is not a transcript |
| Snap | Official 2026 archive and original image/video assets | Exact federal identity joins plus reviewed advocacy payers; the latter require federal-candidate evidence in recovered text; local OCR/ASR; inventory candidates are not all analyzed ads; scheduled dates are not verified daily delivery |
| Meta | Ad Library API | Free identity/developer authorization required; not configured, no acquired-text claim |
| X | Official disclosure documentation/archive links checked | Linked ZIP returns 404; another official host returns 403; CDN response is HTML, not a ZIP; no text acquired |

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
- https://www.jacksonformaine.com/news/
- https://abdulforsenate.com/news/
- https://mikecollinsga.com/
- https://barrforsenate.com/
- https://susancollins.com/
- https://michaelwhatley.com/
- https://www.petericketts.com/
- https://youngkimforcongress.com/
- https://juanciscomani.com/
- https://www.kansansformarshall.com/news
- https://www.lizziefletcher.com/
- https://zachdembo.com/
- https://www.nancylacore.com/media
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
- https://www.lcvvictoryfund.org/
- https://www.rjchq.org/
- https://www.protectfreedompac.com/
- https://www.clubforgrowthaction.com/
- https://www.fec.gov/data/browse-data/
- https://storage.googleapis.com/political-csv/google-political-ads-transparency-bundle.zip
- https://www.facebook.com/ads/library/api/
- https://www.snap.com/political-ads/
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

The current local corpus combines written publisher scripts/quoted ad copy, saved public captions,
reviewed native graphics, Google native previews and Snap native image/video text. Exact totals,
party denominators, distinct exact-message counts, publisher composition and monthly tables are
generated together in `outputs/analysis.json` and `outputs/analysis.html`; the matching
`outputs/analysis-ads.csv` includes complete text and evidence. These files, not an earlier
379-record checkpoint, define the current reconciled local snapshot.

Non-English and uncertain-language records remain in acquisition partitions outside the English
comparison. Twenty-six clear English recovered texts received
contextual language adjudication, bound to exact source hashes in `data/snap-language-reviews.json`.
Original automatic labels remain in segment evidence. This review does not certify OCR accuracy
or the political claims. Other uncertain records are not automatically relabeled English.

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
