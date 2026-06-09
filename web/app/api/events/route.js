const BASE = process.env.AIRTABLE_BASE_ID;
const TOKEN = process.env.AIRTABLE_TOKEN;
const TABLE = "Events";

export const dynamic = "force-dynamic";

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

  const events = records.map((r) => {
    const f = r.fields;
    return {
      id: r.id,
      name: f.Name || "",
      headline: f.headline || "",
      notes: f.Notes || "",
      date: f.date || "",
      state: f.state || "",
      pillars: f.pillars || [],
      activity_type: f.activity_type || "",
      actor_type: f.actor_type || "",
      gov_actor: f.gov_actor || "",
      significance: f.significance || 0,
      why_it_matters: f.why_it_matters || "",
      status: f.Status || "",
      urls: (f.source_urls || "").split("\n").map((s) => s.trim()).filter(Boolean),
      outlets: (f.source_outlets || "").split(",").map((s) => s.trim()).filter(Boolean),
      article_count: f.article_count || 1,
    };
  });

  events.sort((a, b) => (b.date || "").localeCompare(a.date || "") || b.significance - a.significance);
  return Response.json({ events });
}
