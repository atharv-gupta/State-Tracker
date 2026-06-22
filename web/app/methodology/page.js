import usa from "@svg-maps/usa";
import Header from "../header";
import sources from "./sources.json";

export const metadata = {
  title: "Sources & methodology — State Activity Tracker",
};

const STATE_NAMES = Object.fromEntries(usa.locations.map((l) => [l.id.toUpperCase(), l.name]));

const PILLARS = [
  {
    label: "Civil service",
    color: "#059669",
    desc: "How the state hires, classifies, pays, evaluates, and separates its own workforce — and who holds that authority.",
  },
  {
    label: "Procedure",
    color: "#d97706",
    desc: "The government's own procedural and compliance burden — permitting, licensing, reporting, paperwork — added to or stripped back.",
  },
  {
    label: "Digital",
    color: "#2563eb",
    desc: "How the state builds, buys, staffs, and oversees its own technology and data — IT modernization, AI in government, product vs. project.",
  },
  {
    label: "Incentives",
    color: "#7c3aed",
    desc: "The government's learning/feedback loop — outcome-tied funding, oversight, program evaluation, transparency dashboards, follow-up on existing law.",
  },
];

function siteOf(feedUrl) {
  return new URL(feedUrl).origin;
}

export default function Methodology() {
  const newsroomStates = Object.keys(sources.statenewsroom).sort();
  const newspaperStates = Object.keys(sources.newspapers).sort();
  const newspaperCount = newspaperStates.reduce((n, s) => n + sources.newspapers[s].length, 0);
  const total = newsroomStates.length + newspaperCount + sources.national.length;

  return (
    <main className="wrap">
      <Header active="methodology" />

      <div className="method">
        <section className="card msec">
          <h2>What this is</h2>
          <p>
            A weekly, queryable feed of what state governments are actually doing, classified by
            which of RAF&apos;s four state-capacity competencies it advances or undermines — with
            most actions landing outside all four, which is expected:
          </p>
          <ul className="pillarlist">
            {PILLARS.map((p) => (
              <li key={p.label}>
                <span className="chip pillar" style={{ "--c": p.color }}>
                  {p.label}
                </span>{" "}
                {p.desc}
              </li>
            ))}
          </ul>
          <p>
            The tracker covers concrete government <em>actions</em> — bills, vetoes, executive
            orders, rulemaking, appointments, reorganizations, procurement, budgets, program
            launches, audits — not opinion, campaign coverage, or commentary.
          </p>
        </section>

        <section className="card msec">
          <h2>How events get here</h2>
          <ol className="steps">
            <li>
              <strong>Ingest.</strong> Every Monday morning the pipeline fetches {total}{" "}
              state-government news feeds (the full list is below), paging back through each feed
              until it has the past week of articles.
            </li>
            <li>
              <strong>Pre-screen.</strong> A keyword filter for each competency drops clearly
              irrelevant articles before any model is involved.
            </li>
            <li>
              <strong>Gate 1 — provenance (Claude).</strong> Is the underlying activity an action
              by a <em>state-level</em> government actor in their official capacity?
              Federal-only, city-only, opinion, campaign coverage, and private lawsuits fail here.
            </li>
            <li>
              <strong>Gate 2 — competency (Claude).</strong> Does it touch one of the four
              capacities — civil service, procedure, digital, or incentives? Survivors carry state,
              activity type, and actor type into the raw feed; the competency itself is finalized
              per-event in the next step.
            </li>
            <li>
              <strong>De-duplicate &amp; classify.</strong> One government action usually shows up
              across several outlets. A second model pass clusters the articles into distinct events
              (merging every source URL and outlet onto one row — that&apos;s the &ldquo;N articles
              merged&rdquo; note), then classifies each event against RAF&apos;s rubric: its{" "}
              <em>competencies</em> (zero, one, or — when an action genuinely spans two, like
              oversight of a failing IT system — both), a <em>1–3 relevance</em> score for how
              central an example it is (direction-agnostic — undermining a capacity counts as much
              as advancing it), and descriptive <em>topic tags</em>.
            </li>
            <li>
              <strong>Surface.</strong> Events accumulate week over week and are what you see on
              the map.
            </li>
          </ol>
        </section>

        <section className="card msec">
          <h2>Sources</h2>
          <p>
            <strong>{total} feeds</strong> in three layers, each doing a different job:{" "}
            {newsroomStates.length} States Newsroom outlets + {newspaperCount} newspapers and
            outlets + {sources.national.length} trade press. The registry is a living list — feeds
            were RSS-verified on {sources.verified}; dead feeds get pruned and new outlets added as
            found.
          </p>

          <h3>Layer 1 — Spine: States Newsroom ({newsroomStates.length} states)</h3>
          <p className="muted">
            Nonprofit statehouse newsrooms, one per state. Dedicated, consistent coverage of state
            government.
          </p>
          <table className="srctable">
            <thead>
              <tr>
                <th>State</th>
                <th>Outlet</th>
              </tr>
            </thead>
            <tbody>
              {newsroomStates.map((st) => (
                <tr key={st}>
                  <td>{STATE_NAMES[st] || st}</td>
                  <td>
                    <a href={`https://${sources.statenewsroom[st]}`} target="_blank" rel="noreferrer">
                      {sources.statenewsroom[st]}
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3>Layer 2 — Breadth: state newspapers &amp; outlets ({newspaperCount} feeds)</h3>
          <p className="muted">
            Complementary coverage per state, and the only layer covering the{" "}
            {50 - newsroomStates.length} states with no States Newsroom outlet (
            {newspaperStates.filter((s) => !sources.statenewsroom[s]).join(", ")}).
          </p>
          <table className="srctable">
            <thead>
              <tr>
                <th>State</th>
                <th>Outlets</th>
              </tr>
            </thead>
            <tbody>
              {newspaperStates.map((st) => (
                <tr key={st}>
                  <td>{STATE_NAMES[st] || st}</td>
                  <td>
                    {sources.newspapers[st].map((o, i) => (
                      <span key={o.name}>
                        {i > 0 ? " · " : ""}
                        <a href={siteOf(o.feed_url)} target="_blank" rel="noreferrer">
                          {o.name}
                        </a>
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3>Layer 3 — Trade press (national)</h3>
          <ul>
            {sources.national.map((o) => (
              <li key={o.name}>
                <a href={siteOf(o.feed_url)} target="_blank" rel="noreferrer">
                  {o.name}
                </a>{" "}
                — dense digital-pillar coverage; the classifier infers the state from the article.
              </li>
            ))}
          </ul>
        </section>

        <section className="card msec">
          <h2>Known gaps</h2>
          <ul>
            <li>
              <strong>Feed retention.</strong> Over half of these feeds hold less than 7 days of
              history. The pipeline pages backwards where the feed supports it, but short
              non-paginating feeds (public radio, some metro dailies) can still lose items between
              weekly runs.
            </li>
            <li>
              <strong>Indiana</strong> has only one complementary outlet — most Indiana papers are
              Gannett, which removed RSS.
            </li>
            <li>
              <strong>Coverage follows the press.</strong> An event only enters the tracker if an
              outlet wrote about it; states with thinner statehouse press will look quieter than
              they are.
            </li>
          </ul>
        </section>
      </div>
    </main>
  );
}
