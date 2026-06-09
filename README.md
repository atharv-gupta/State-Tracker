# State Activity Tracker

A weekly, queryable feed of what state governments are actually doing, categorized into RAF's pillars: **procedure** (deproceduralization / regulatory simplification), **digital** (digital & tech transformation), and **civil-service** (civil service & workforce reform).

The pipeline ingests ~170 state-government news feeds, keeps only items that represent real government activity in those pillars, de-duplicates them into distinct *events*, stores everything in Airtable, and surfaces a filterable map view on the web.

## How it works

```
[Ingest]            [Classify + gate]        [Store raw]      [Dedupe]            [Surface]
171 RSS feeds  -->  keyword pre-screen  -->  'Raw Events' --> cluster same   -->  'Events' table
last N days         + 2 LLM gates            one row per     event across         one row per event
                    (provenance, pillar)     article          outlets (Sonnet)    + web map view
```

1. **`pipeline.py`** — fetches every feed in `sources.py` (paging back through WordPress feeds until past the lookback window, since many feeds retain <7 days), keeps items from the last N days, pre-screens with pillar keywords (cheap, before any LLM call), then gates each survivor with Claude Haiku:
   - **Gate 1 (provenance):** is the underlying activity an action by a *state-level* government actor in their official capacity? Bills, vetoes, EOs, rulemaking, appointments, reorgs, procurement, budgets, program launches, audits. Federal-only, city-only, opinion, campaign coverage, and private lawsuits fail.
   - **Gate 2 (pillar):** does it touch procedure / digital / civil-service?
   - Survivors land in the **`Raw Events`** Airtable table, one row per article, tagged with state, pillars, activity type, actor type, and significance (1–5, a ranking — never a drop gate).
2. **`dedupe.py`** — clusters the window's raw rows (one government action shows up across many outlets) with Claude Sonnet and rebuilds that window of the **`Events`** table: one row per event, all source URLs/outlets merged. Rows outside the window are never touched, so the table accumulates history week over week.
3. **`web/`** — Next.js app: US map shaded by event count, filters for time window (week / month / all), pillar, activity type, and government actor type, with an event list beneath. Reads Airtable server-side via `/api/events` (the token never reaches the browser).

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env_example .env   # fill in the three values
```

`.env` needs `ANTHROPIC_API_KEY`, `AIRTABLE_TOKEN` (scopes: data.records read/write, schema.bases read/write), and `AIRTABLE_BASE_ID`. Tables and fields are created automatically if missing.

Run manually:

```bash
.venv/bin/python pipeline.py --days 7    # ingest the past week into Raw Events
.venv/bin/python dedupe.py --days 7      # cluster that window into Events
```

Useful flags: `pipeline.py CO KS --dry-run --limit 20` (specific states, no writes, capped LLM calls) for tuning sessions; `--days 31` for backfills (bounded by feed retention — most feeds can't reach back more than a few weeks even with pagination).

Web view:

```bash
cd web && npm install
cp ../.env  .env.local   # or create .env.local with AIRTABLE_TOKEN + AIRTABLE_BASE_ID
npm run dev              # http://localhost:3000
```

## Weekly automation

`.github/workflows/weekly.yml` runs ingest + dedupe every Monday 13:00 UTC (~7am MT), and can be triggered manually from the Actions tab. To activate, add the three repo secrets on GitHub: **Settings → Secrets and variables → Actions → New repository secret** for `ANTHROPIC_API_KEY`, `AIRTABLE_TOKEN`, `AIRTABLE_BASE_ID`.

## Deploying the web view (Vercel)

1. [vercel.com](https://vercel.com) → Add New → Project → import this GitHub repo.
2. Set **Root Directory** to `web/`.
3. Add environment variables `AIRTABLE_TOKEN` and `AIRTABLE_BASE_ID`.
4. Deploy. Every push to `main` redeploys automatically.

## Sources

Three layers, each doing a different job (see `SPEC.md` §4). The registry lives in `sources.py` and is a **living artifact** — feeds were RSS-verified on 2026-06-09; prune dead ones and add new outlets as found. The pillar keyword lists at the top of `pipeline.py` are the other living artifact: misses come from missing keywords, not missing outlets.

The web view's **Sources & methodology** tab renders a snapshot of this registry. After editing `sources.py`, regenerate it with `python sources.py --json > web/app/methodology/sources.json`.

<!-- SOURCES:BEGIN (generated from sources.py) -->

**171 feeds total** — 39 States Newsroom + 131 newspapers/outlets + 1 trade press.

### Layer 1 — Spine: States Newsroom (39 states)

Nonprofit statehouse newsrooms, one per state, pulled at `https://<domain>/feed/localFeed`.

| State | Outlet |
|---|---|
| AK | [alaskabeacon.com](https://alaskabeacon.com) |
| AL | [alabamareflector.com](https://alabamareflector.com) |
| AR | [arkansasadvocate.com](https://arkansasadvocate.com) |
| AZ | [azmirror.com](https://azmirror.com) |
| CO | [coloradonewsline.com](https://coloradonewsline.com) |
| FL | [floridaphoenix.com](https://floridaphoenix.com) |
| GA | [georgiarecorder.com](https://georgiarecorder.com) |
| IA | [iowacapitaldispatch.com](https://iowacapitaldispatch.com) |
| ID | [idahocapitalsun.com](https://idahocapitalsun.com) |
| IN | [indianacapitalchronicle.com](https://indianacapitalchronicle.com) |
| KS | [kansasreflector.com](https://kansasreflector.com) |
| KY | [kentuckylantern.com](https://kentuckylantern.com) |
| LA | [lailluminator.com](https://lailluminator.com) |
| MD | [marylandmatters.org](https://marylandmatters.org) |
| ME | [mainemorningstar.com](https://mainemorningstar.com) |
| MI | [michiganadvance.com](https://michiganadvance.com) |
| MN | [minnesotareformer.com](https://minnesotareformer.com) |
| MO | [missouriindependent.com](https://missouriindependent.com) |
| MT | [dailymontanan.com](https://dailymontanan.com) |
| NC | [ncnewsline.com](https://ncnewsline.com) |
| ND | [northdakotamonitor.com](https://northdakotamonitor.com) |
| NE | [nebraskaexaminer.com](https://nebraskaexaminer.com) |
| NH | [newhampshirebulletin.com](https://newhampshirebulletin.com) |
| NJ | [newjerseymonitor.com](https://newjerseymonitor.com) |
| NM | [sourcenm.com](https://sourcenm.com) |
| NV | [nevadacurrent.com](https://nevadacurrent.com) |
| OH | [ohiocapitaljournal.com](https://ohiocapitaljournal.com) |
| OK | [oklahomavoice.com](https://oklahomavoice.com) |
| OR | [oregoncapitalchronicle.com](https://oregoncapitalchronicle.com) |
| PA | [penncapital-star.com](https://penncapital-star.com) |
| RI | [rhodeislandcurrent.com](https://rhodeislandcurrent.com) |
| SC | [scdailygazette.com](https://scdailygazette.com) |
| SD | [southdakotasearchlight.com](https://southdakotasearchlight.com) |
| TN | [tennesseelookout.com](https://tennesseelookout.com) |
| UT | [utahnewsdispatch.com](https://utahnewsdispatch.com) |
| VA | [virginiamercury.com](https://virginiamercury.com) |
| WA | [washingtonstatestandard.com](https://washingtonstatestandard.com) |
| WI | [wisconsinexaminer.com](https://wisconsinexaminer.com) |
| WV | [westvirginiawatch.com](https://westvirginiawatch.com) |

### Layer 2 — Breadth: state newspapers & outlets (RSS-verified 2026-06-09)

Complementary coverage per state; the only layer covering the 11 states with no States Newsroom outlet (CA, CT, DE, HI, IL, MA, MS, NY, TX, VT, WY).

| State | Outlets |
|---|---|
| AK | [Anchorage Daily News](https://www.adn.com/arc/outboundfeeds/rss/?outputType=xml), [Juneau Empire](https://www.juneauempire.com/feed/) |
| AL | [Alabama Daily News](https://aldailynews.com/feed/), [Alabama Political Reporter](https://www.alreporter.com/feed/), [AL.com](https://www.al.com/arc/outboundfeeds/rss/?outputType=xml) |
| AR | [Arkansas Times](https://arktimes.com/feed), [Talk Business & Politics](https://talkbusiness.net/feed/) |
| AZ | [Arizona Capitol Times](https://azcapitoltimes.com/feed/), [KJZZ](https://www.kjzz.org/politics.rss) |
| CA | [CalMatters](https://calmatters.org/feed/), [Capitol Weekly](https://capitolweekly.net/feed/), [LA Times Politics](https://www.latimes.com/politics/rss2.0.xml) |
| CO | [The Colorado Sun](https://coloradosun.com/feed/), [Colorado Politics](https://www.coloradopolitics.com/feed/) |
| CT | [CT Mirror](https://ctmirror.org/feed/), [CT News Junkie](https://ctnewsjunkie.com/feed/) |
| DE | [Spotlight Delaware](https://spotlightdelaware.org/feed/), [Delaware Public Media](https://www.delawarepublic.org/politics-government.rss), [WHYY Delaware](https://whyy.org/feed/) |
| FL | [Florida Politics](https://floridapolitics.com/feed/), [Tampa Bay Times](https://www.tampabay.com/arc/outboundfeeds/rss/?outputType=xml), [WUSF](https://www.wusf.org/politics-issues.rss) |
| GA | [Capitol Beat News Service](https://capitol-beat.org/feed/), [Georgia Public Broadcasting](https://www.gpb.org/rss), [Atlanta Civic Circle](https://atlantaciviccircle.org/feed/) |
| HI | [Honolulu Civil Beat](https://www.civilbeat.org/feed/), [Hawaii Public Radio](https://www.hawaiipublicradio.org/local-news.rss), [Star-Advertiser](https://www.staradvertiser.com/feed/) |
| IA | [Radio Iowa](https://www.radioiowa.com/feed/), [Iowa Public Radio](https://www.iowapublicradio.org/ipr-news.rss), [Bleeding Heartland](https://www.bleedingheartland.com/feed/) |
| ID | [Idaho Education News](https://www.idahoednews.org/feed/), [Boise State Public Radio](https://www.boisestatepublicradio.org/news.rss) |
| IL | [Capitol News Illinois](https://capitolnewsillinois.com/feed/), [NPR Illinois](https://www.nprillinois.org/illinois.rss), [Chicago Sun-Times](https://chicago.suntimes.com/feed) |
| IN | [Indiana Public Media](https://indianapublicmedia.org/index.rss) |
| KS | [KCUR](https://www.kcur.org/politics-elections-and-government.rss), [KSNT](https://www.ksnt.com/feed/), [Sunflower State Journal](https://sunflowerstatejournal.com/feed/) |
| KY | [Kentucky Public Radio](https://www.lpm.org/news.rss), [Link NKY](https://linknky.com/feed/) |
| LA | [Louisiana Radio Network](https://louisianaradionetwork.com/feed/), [WWNO](https://www.wwno.org/politics.rss) |
| MA | [CommonWealth Beacon](https://commonwealthbeacon.org/feed/), [GBH News](https://www.wgbh.org/news/politics.rss), [MassLive](https://www.masslive.com/arc/outboundfeeds/rss/?outputType=xml) |
| MD | [Baltimore Banner](https://www.thebaltimorebanner.com/arc/outboundfeeds/rss/?outputType=xml), [WYPR](https://www.wypr.org/index.rss), [Maryland Reporter](https://marylandreporter.com/feed/) |
| ME | [Portland Press Herald](https://www.pressherald.com/feed/), [Bangor Daily News](https://www.bangordailynews.com/feed/), [Maine Public](https://www.mainepublic.org/politics.rss) |
| MI | [Bridge Michigan](https://www.bridgemi.com/rss.xml), [Michigan Public](https://www.michiganpublic.org/politics-government.rss), [MLive](https://www.mlive.com/arc/outboundfeeds/rss/?outputType=xml) |
| MN | [MinnPost](https://www.minnpost.com/feed/), [Star Tribune](https://www.startribune.com/rss/) |
| MO | [St. Louis Public Radio](https://www.stlpr.org/government-politics-issues.rss), [Missourinet](https://www.missourinet.com/feed/), [St. Louis Post-Dispatch](https://www.stltoday.com/search/?f=rss) |
| MS | [Mississippi Today](https://mississippitoday.org/feed/), [Magnolia Tribune](https://magnoliatribune.com/feed/), [Mississippi Free Press](https://www.mississippifreepress.org/feed/) |
| MT | [Montana Free Press](https://montanafreepress.org/feed/), [Montana Public Radio](https://www.mtpr.org/montana-news.rss) |
| NC | [The Assembly](https://www.theassemblync.com/feed/), [WUNC](https://www.wunc.org/politics.rss), [WRAL](https://www.wral.com/news/rss/142/) |
| ND | [InForum](https://www.inforum.com/index.rss), [Prairie Public](https://news.prairiepublic.org/local-news.rss), [KFYR](https://www.kfyrtv.com/arc/outboundfeeds/rss/?outputType=xml) |
| NE | [Flatwater Free Press](https://flatwaterfreepress.org/feed/), [KETV](https://www.ketv.com/topstories-rss) |
| NH | [NHPR](https://www.nhpr.org/nh-news.rss), [InDepthNH](https://indepthnh.org/feed/), [NH Journal](https://nhjournal.com/feed/) |
| NJ | [NJ Spotlight News](https://www.njspotlightnews.org/feed/), [New Jersey Globe](https://newjerseyglobe.com/feed/), [NJ.com](https://www.nj.com/arc/outboundfeeds/rss/?outputType=xml) |
| NM | [NM Political Report](https://nmpoliticalreport.com/feed/), [KUNM](https://www.kunm.org/local-news.rss) |
| NV | [The Nevada Independent](https://thenevadaindependent.com/feed), [Las Vegas Review-Journal](https://www.reviewjournal.com/feed/) |
| NY | [New York Focus](https://nysfocus.com/feed), [City & State NY](https://www.cityandstateny.com/rss/all/), [Gothamist](https://gothamist.com/feed) |
| OH | [Statehouse News Bureau](https://www.statenews.org/government-politics.rss), [Signal Ohio](https://signalohio.org/feed/), [Signal Cleveland](https://signalcleveland.org/feed/) |
| OK | [The Journal Record](https://journalrecord.com/feed/), [NonDoc](https://nondoc.com/feed/), [Oklahoma Watch](https://oklahomawatch.org/feed/) |
| OR | [OPB](https://www.opb.org/arc/outboundfeeds/rss/?outputType=xml), [Willamette Week](https://www.wweek.com/arc/outboundfeeds/rss/?outputType=xml), [The Oregonian](https://www.oregonlive.com/arc/outboundfeeds/rss/?outputType=xml) |
| PA | [WHYY](https://whyy.org/categories/politics-policy/feed/), [PennLive](https://www.pennlive.com/arc/outboundfeeds/rss/?outputType=xml), [WESA](https://www.wesa.fm/politics-government.rss) |
| RI | [The Public's Radio](https://thepublicsradio.org/feed/), [Providence Business News](https://pbn.com/feed/), [WPRI](https://www.wpri.com/feed/) |
| SC | [FITSNews](https://www.fitsnews.com/feed/), [SC Public Radio](https://www.southcarolinapublicradio.org/sc-news.rss) |
| SD | [KELOLAND](https://www.keloland.com/feed/), [Mitchell Republic](https://www.mitchellrepublic.com/index.rss), [Dakota News Now](https://www.dakotanewsnow.com/arc/outboundfeeds/rss/?outputType=xml) |
| TN | [Nashville Banner](https://nashvillebanner.com/feed/), [WPLN](https://wpln.org/feed/) |
| TX | [Texas Tribune](https://www.texastribune.org/feeds/main/), [Texas Observer](https://www.texasobserver.org/feed/), [Texas Standard](https://www.texasstandard.org/feed/) |
| UT | [KUER](https://www.kuer.org/politics-government.rss), [The Salt Lake Tribune](https://www.sltrib.com/arc/outboundfeeds/rss/?outputType=xml), [Utah Policy](https://utahpolicy.com/feed/) |
| VA | [Cardinal News](https://cardinalnews.org/feed/), [Virginia Business](https://virginiabusiness.com/feed/), [VPM](https://www.vpm.org/news.rss) |
| VT | [VTDigger](https://vtdigger.org/feed/), [Seven Days](https://www.sevendaysvt.com/vermont/Rss.xml) |
| WA | [Washington Observer](https://washingtonobserver.substack.com/feed), [Cascade PBS](https://crosscut.com/rss) |
| WI | [Wisconsin Watch](https://wisconsinwatch.org/feed/), [Urban Milwaukee](https://urbanmilwaukee.com/feed/), [WPR](https://www.wpr.org/feed) |
| WV | [Mountain State Spotlight](https://mountainstatespotlight.org/feed/), [WV MetroNews](https://wvmetronews.com/feed/), [Charleston Gazette-Mail](https://www.wvgazettemail.com/search/?f=rss&c=news/politics) |
| WY | [WyoFile](https://wyofile.com/feed/), [Wyoming Public Media](https://www.wyomingpublicmedia.org/rss.xml), [Oil City News](https://oilcity.news/feed/) |

### Layer 3 — Trade press (national)

- [StateScoop](https://statescoop.com/feed/) — dense digital-pillar coverage; the classifier infers the state.
<!-- SOURCES:END -->

### Known gaps & gotchas

- **Feed retention:** 94 of 171 feeds hold less than 7 days of history. WordPress feeds are paginated backwards automatically; non-WordPress short feeds (public radio, Arc-platform papers) can still lose items between weekly runs. Running the ingest daily (dedupe stays weekly) closes this — a one-line cron change in `weekly.yml`.
- **Indiana** has only one verified complementary outlet (most Indiana papers are Gannett, which removed RSS).
- **StateScoop** retains only ~10 items (~a week of their publishing volume).
- `phase0.py` is the original single-feed prototype (Google News query approach) — superseded, kept for reference. The Google News index layer is the planned Phase 1 completeness guarantee.

## Data model

One row per event in `Events`: `Name`, `Notes`, `date`, `state`, `pillars` (multi), `activity_type` (bill-introduced/bill-passed/veto/EO/rulemaking/appointment/reorg/RFP-procurement/budget/program-launch/audit-report), `actor_type` (governor/legislature/state agency/statewide official/board-commission/court/university system), `gov_actor`, `significance` (1–5), `why_it_matters`, `source_urls`, `source_outlets`, `article_count`, `Status`.
