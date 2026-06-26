const BASE = process.env.AIRTABLE_BASE_ID;
const TOKEN = process.env.AIRTABLE_TOKEN;
const TABLE = "State Specs";

export const dynamic = "force-dynamic";

// Every field in the State Specs table, passed through verbatim. The UI decides
// what to render; blanks are simply omitted client-side.
const FIELDS = [
  "state", "postal",
  "partisan_lean", "partisan_lean_basis", "trifecta",
  "governor_name", "governor_party", "gov_term_limit", "gov_terms_remaining",
  "gov_next_election", "basic_source", "basic_asof",
  "collective_bargaining", "cb_note", "hr_authority_model", "merit_protection",
  "napa_note", "civilservice_source", "civilservice_asof",
  "ai_leadership", "digital_service_team", "digital_source", "digital_asof",
  "rulemaking_form", "executive_review", "executive_review_who",
  "legislative_review", "independent_agency_review", "impact_analysis",
  "periodic_review", "procedure_source", "procedure_asof",
];

export async function GET() {
  if (!BASE || !TOKEN) {
    return Response.json({ error: "Missing AIRTABLE_TOKEN / AIRTABLE_BASE_ID" }, { status: 500 });
  }

  const records = [];
  let offset;
  do {
    const url = new URL(`https://api.airtable.com/v0/${BASE}/${encodeURIComponent(TABLE)}`);
    url.searchParams.set("pageSize", "100");
    if (offset) url.searchParams.set("offset", offset);
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${TOKEN}` },
      cache: "no-store",
    });
    if (!res.ok) {
      return Response.json({ error: `Airtable ${res.status}` }, { status: 502 });
    }
    const data = await res.json();
    records.push(...data.records);
    offset = data.offset;
  } while (offset);

  const states = records.map((r) => {
    const out = {};
    for (const k of FIELDS) {
      const v = r.fields[k];
      if (v !== undefined && v !== null && v !== "") out[k] = v;
    }
    return out;
  });

  states.sort((a, b) => (a.state || "").localeCompare(b.state || ""));
  return Response.json({ states });
}
