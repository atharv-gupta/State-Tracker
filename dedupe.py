#!/usr/bin/env python3
"""State Activity Tracker — dedupe/condense stage (clean layer).

Reads the last N days of 'Raw Events' (one row per article), clusters rows
that describe the same underlying government action into a single EVENT
(one government action shows up across many outlets — SPEC.md §4 principle 1),
and rebuilds that window of the clean 'Events' table: one row per event with
all source URLs/outlets merged.

Usage:
    python dedupe.py                # cluster the last 7 days
    python dedupe.py --days 14
    python dedupe.py --dry-run      # show clusters, don't touch Airtable
"""

import argparse
import concurrent.futures
import json
import os
import sys
import uuid
from datetime import date, timedelta

from anthropic import Anthropic
from dotenv import load_dotenv
from pyairtable import Api

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID")
if not all([ANTHROPIC_API_KEY, AIRTABLE_TOKEN, AIRTABLE_BASE_ID]):
    sys.exit("Missing env vars; see .env_example.")

RAW_TABLE = "Raw Events"
CLEAN_TABLE = "Events"
MODEL = "claude-sonnet-4-6"   # stronger model for the synthesis step
WORKERS = 6

PILLAR_CHOICES = ["procedure", "digital", "civil-service"]
ACTIVITY_TYPE_CHOICES = [
    "bill-introduced", "bill-passed", "veto", "EO", "rulemaking", "appointment",
    "reorg", "RFP/procurement", "budget", "program-launch", "audit/report",
]
ACTOR_TYPE_CHOICES = [
    "governor", "legislature", "state agency", "statewide official",
    "board/commission", "court", "university system", "other",
]

SYSTEM_PROMPT = f"""You deduplicate rows in a state-government activity tracker.
You receive a list of articles (rows) about ONE state's government from the
past week. Multiple rows often describe the SAME underlying government action
reported by different outlets. Cluster them into distinct EVENTS.

Rules:
- Two rows belong to the same event only if they describe the same underlying
  government action (same bill, same appointment, same layoff, same contract),
  not merely the same topic.
- The same bill/action at different procedural stages within the week is ONE
  event at its latest stage; note the progression in the notes.
- Every input row id must appear in exactly one event.
- A row that matches nothing is its own single-row event.

Output ONLY this JSON (no fences, no preamble):
{{
  "events": [
    {{
      "member_ids": ["rec...", "rec..."],
      "name": "concise title of the action, 5-10 words, no state name, sentence case",
      "headline": "one-line what happened, best synthesis of the member rows",
      "notes": "1-2 plain sentences: what happened and why it matters for state capacity",
      "date": "YYYY-MM-DD of the government action (earliest credible)",
      "pillars": ["one or more of: {' | '.join(PILLAR_CHOICES)}"],
      "activity_type": "one of: {' | '.join(ACTIVITY_TYPE_CHOICES)}",
      "gov_actor": "which body/office acted",
      "actor_type": "one of: {' | '.join(ACTOR_TYPE_CHOICES)}",
      "significance": 3,
      "why_it_matters": "one line for the digest, empty string if none",
      "status": "optional: introduced | enacted | etc., empty string if N/A"
    }}
  ]
}}"""


def parse_json_response(text):
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    start = text.find("{")
    end = text.rfind("}")
    return json.loads(text[start:end + 1])


def cluster_state(client, state, rows):
    """rows: list of (record_id, fields). Returns the model's event list."""
    payload = [{
        "id": rid,
        "date": f.get("date", ""),
        "headline": f.get("headline", ""),
        "gov_actor": f.get("gov_actor", ""),
        "activity_type": f.get("activity_type", ""),
        "actor_type": f.get("actor_type", ""),
        "pillars": f.get("pillars", []),
        "notes": f.get("Notes", ""),
        "significance": f.get("significance", ""),
        "status": f.get("Status") or f.get("status", ""),
        "outlet": f.get("source_outlets", ""),
        "url": f.get("source_urls", ""),
    } for rid, f in rows]
    resp = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": json.dumps({"state": state, "rows": payload})}],
    )
    return parse_json_response(resp.content[0].text)["events"]


def build_event_row(state, ev, members):
    pillars = ev.get("pillars") or []
    if isinstance(pillars, str):
        pillars = [pillars]
    pillars = [p for p in pillars if p in PILLAR_CHOICES]
    if not pillars:
        pillars = sorted({p for _, f in members for p in f.get("pillars", [])})

    urls, outlets, types = [], [], []
    for _, f in members:
        for u in (f.get("source_urls") or "").splitlines():
            if u.strip() and u.strip() not in urls:
                urls.append(u.strip())
        o = f.get("source_outlets", "")
        if o and o not in outlets:
            outlets.append(o)
        st = f.get("source_type", "")
        if st and st not in types:
            types.append(st)

    row = {
        "Name": f"{state} — {(ev.get('name') or ev.get('headline', '')).strip()}",
        "Notes": (ev.get("notes") or "").strip(),
        "event_id": str(uuid.uuid4()),
        "state": state,
        "headline": ev.get("headline", ""),
        "gov_actor": ev.get("gov_actor", ""),
        "why_it_matters": ev.get("why_it_matters", ""),
        "Status": ev.get("status", ""),
        "source_urls": "\n".join(urls),
        "source_outlets": ", ".join(outlets),
        "source_type": ", ".join(types),
        "article_count": len(members),
    }
    if pillars:
        row["pillars"] = pillars

    d = ev.get("date", "")
    if len(d) == 10 and d[4] == "-" and d[7] == "-":
        row["date"] = d
    else:
        dates = sorted(f.get("date", "") for _, f in members if f.get("date"))
        if dates:
            row["date"] = dates[0]

    at = ev.get("activity_type", "")
    if at in ACTIVITY_TYPE_CHOICES:
        row["activity_type"] = at

    actor = ev.get("actor_type", "")
    if actor not in ACTOR_TYPE_CHOICES:
        actor = next((f.get("actor_type") for _, f in members
                      if f.get("actor_type") in ACTOR_TYPE_CHOICES), "other")
    row["actor_type"] = actor

    try:
        sig = int(ev.get("significance") or 0)
        if 1 <= sig <= 5:
            row["significance"] = sig
    except (TypeError, ValueError):
        pass

    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=7, help="window in days (default 7)")
    ap.add_argument("--dry-run", action="store_true", help="show clusters, don't write")
    args = ap.parse_args()

    min_date = (date.today() - timedelta(days=args.days)).isoformat()

    api = Api(AIRTABLE_TOKEN)
    base = api.base(AIRTABLE_BASE_ID)
    schema = base.schema()
    raw = base.table(next(t.id for t in schema.tables if t.name == RAW_TABLE))
    clean = base.table(next(t.id for t in schema.tables if t.name == CLEAN_TABLE))

    rows = [(r["id"], r["fields"]) for r in raw.all()
            if (r["fields"].get("date") or "") >= min_date]
    print(f"{len(rows)} raw rows since {min_date}")
    if not rows:
        return

    by_state = {}
    for rid, f in rows:
        by_state.setdefault(f.get("state", "??"), []).append((rid, f))

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    all_events, errors = [], []

    def work(item):
        state, srows = item
        if len(srows) == 1:
            rid, f = srows[0]
            ev = {
                "member_ids": [rid],
                "name": (f.get("Name", "").split("—", 1) + [""])[1].strip() or f.get("headline", ""),
                "headline": f.get("headline", ""),
                "notes": f.get("Notes", ""),
                "date": f.get("date", ""),
                "pillars": f.get("pillars", []),
                "activity_type": f.get("activity_type", ""),
                "gov_actor": f.get("gov_actor", ""),
                "significance": f.get("significance", ""),
                "why_it_matters": f.get("why_it_matters", ""),
                "status": f.get("Status") or f.get("status", ""),
            }
            return state, [ev], srows
        return state, cluster_state(client, state, srows), srows

    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(work, item): item[0] for item in by_state.items()}
        for fut in concurrent.futures.as_completed(futs):
            state = futs[fut]
            try:
                state, events, srows = fut.result()
            except Exception as e:
                errors.append(f"{state}: {e}")
                print(f"  ERROR {state} — {e}")
                continue
            by_id = dict(srows)
            ids_seen = set()
            for ev in events:
                members = [(rid, by_id[rid]) for rid in ev.get("member_ids", []) if rid in by_id]
                if not members:
                    continue
                ids_seen.update(rid for rid, _ in members)
                all_events.append((state, ev, members))
            orphans = [rid for rid in by_id if rid not in ids_seen]
            for rid in orphans:   # model missed a row — keep it as its own event
                f = by_id[rid]
                all_events.append((state, {
                    "member_ids": [rid], "headline": f.get("headline", ""),
                    "name": f.get("headline", ""), "notes": f.get("Notes", ""),
                    "date": f.get("date", ""), "pillars": f.get("pillars", []),
                    "activity_type": f.get("activity_type", ""),
                    "gov_actor": f.get("gov_actor", ""),
                    "significance": f.get("significance", ""),
                    "why_it_matters": f.get("why_it_matters", ""),
                    "status": f.get("Status") or f.get("status", ""),
                }, [(rid, f)]))
            merged = sum(1 for ev in events if len(ev.get("member_ids", [])) > 1)
            print(f"  {state}: {len(srows)} articles -> {len(events) + len(orphans)} events"
                  + (f" ({merged} merged clusters)" if merged else ""))

    print(f"\n{len(rows)} raw articles -> {len(all_events)} events")

    if args.dry_run:
        for state, ev, members in sorted(all_events, key=lambda x: (x[0], x[1].get("date", ""))):
            tag = f"x{len(members)}" if len(members) > 1 else "  "
            print(f"  {state} {ev.get('date','??')} {tag} {ev.get('headline','')[:90]}")
        return

    # Rebuild the clean table's window: delete clean rows in range, write fresh
    stale = [r["id"] for r in clean.all()
             if (r["fields"].get("date") or "") >= min_date or not r["fields"].get("date")]
    if stale:
        clean.batch_delete(stale)
        print(f"Cleared {len(stale)} stale clean rows in window")

    created = 0
    for state, ev, members in all_events:
        try:
            clean.create(build_event_row(state, ev, members), typecast=True)
            created += 1
        except Exception as e:
            errors.append(f"write {state}: {e}")
            print(f"  ERROR writing {state} — {e}")
    print(f"Wrote {created} events to '{CLEAN_TABLE}'")

    if errors:
        print("\n--- ERRORS ---")
        for e in errors:
            print(f"  {e}")


if __name__ == "__main__":
    main()
