#!/usr/bin/env python3
"""State Activity Tracker — weekly email digest.

Runs right after dedupe.py each week: reads the last N days of the clean
'Events' table, selects the most notable events per competency (see §3 of
digest_feature_brief.md), composes one HTML+text email, and sends it via Resend.

Phase 1: single hard-coded recipient (the Resend account address), sending from
Resend's pre-verification sender. The recipient source (get_recipients) and the
provider call (send_email) are isolated so a subscriber model / real domain can
drop in later without touching selection or formatting.

Usage:
    python digest.py --days 7              # compose + send to RECIPIENTS
    python digest.py --days 7 --dry-run    # render + per-category counts, send nothing
    python digest.py --days 7 --to me@x.com  # override recipient (post-DNS only)
"""

import argparse
import os
import re
import sys
from datetime import date, datetime, timedelta
from html import escape

import requests
from dotenv import load_dotenv
from pyairtable import Api

load_dotenv()

AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
DIGEST_FROM = os.environ.get("DIGEST_FROM", "onboarding@resend.dev")

EVENTS_TABLE = "Events"

# Public read-only tracker (overridable via env). Linked at the foot of the digest.
TRACKER_URL = os.environ.get("TRACKER_URL", "https://state-tracker-e2i7.vercel.app/")

# Snippy opener.
INTRO = ("Here's everything you need to know about what states got up to last week "
         "in the world of state capacity.")

# §0 pre-DNS constraint: Resend can only deliver to the account's own address
# until a domain is verified. Do not add other recipients yet — they 403.
RECIPIENTS = ["atharv@recodingamerica.fund"]

# §3 — fixed section order; values match the Events `competency` field exactly.
COMPETENCIES = ["civil-service", "procedure", "digital", "incentives"]
COMPETENCY_LABELS = {
    "civil-service": "Civil service",
    "procedure": "Procedure",
    "digital": "Digital",
    "incentives": "Incentives",
}

# §4 — an event spanning two competencies appears in each relevant section.
# Flip to True later to show it only in its first section.
DEDUPE_ACROSS_SECTIONS = False


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #

def date_epoch(iso: str) -> int:
    """ISO date (YYYY-MM-DD) -> epoch days, for sorting. 0 if unparseable."""
    try:
        return (datetime.strptime(iso, "%Y-%m-%d").date() - date(1970, 1, 1)).days
    except (ValueError, TypeError):
        return 0


def load_events(days: int) -> list[dict]:
    """Read the Events table, keep rows whose `date` is within the last `days`."""
    if not all([AIRTABLE_TOKEN, AIRTABLE_BASE_ID]):
        sys.exit("Missing AIRTABLE_TOKEN / AIRTABLE_BASE_ID; see .env_example.")
    api = Api(AIRTABLE_TOKEN)
    table = api.table(AIRTABLE_BASE_ID, EVENTS_TABLE)
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    events = []
    for rec in table.all():
        f = rec["fields"]
        d = f.get("date", "")
        if not d or d < cutoff:
            continue
        outlets = [o.strip() for o in (f.get("source_outlets") or "").split(",") if o.strip()]
        urls = [u.strip() for u in (f.get("source_urls") or "").splitlines() if u.strip()]
        rel = f.get("relevance")
        try:
            rel = int(rel)
        except (TypeError, ValueError):
            rel = 0
        events.append({
            "name": (f.get("Name") or "").strip(),
            "competency": f.get("competency") or [],
            "relevance": rel,
            "article_count": int(f.get("article_count") or 1),
            "date": d,
            "date_epoch": date_epoch(d),
            "state": f.get("state") or "",
            "activity_type": f.get("activity_type") or "",
            "gov_actor": f.get("gov_actor") or "",
            "why_it_matters": (f.get("why_it_matters") or "").strip(),
            "notes": (f.get("Notes") or "").strip(),
            "source_outlets": outlets,
            "source_urls": urls,
        })
    return events


# --------------------------------------------------------------------------- #
# Selection (§3 / §4)
# --------------------------------------------------------------------------- #

def rank(e: dict):
    """§4: 2's ordered most-covered then most-recent (they get truncated)."""
    return (-e["article_count"], -e["date_epoch"])


def select(events: list[dict], comp: str) -> list[dict]:
    in_comp = [e for e in events if comp in (e["competency"] or [])]
    threes = [e for e in in_comp if e["relevance"] == 3]
    twos = sorted((e for e in in_comp if e["relevance"] == 2), key=rank)
    selected = list(threes)                 # all 3's, unconditionally
    i = 0
    while len(selected) <= 4 and i < len(twos):
        selected.append(twos[i])
        i += 1
    return selected


def select_all(events: list[dict]) -> dict[str, list[dict]]:
    """Per-competency selection, honoring DEDUPE_ACROSS_SECTIONS."""
    out = {}
    seen = set()
    for comp in COMPETENCIES:
        chosen = select(events, comp)
        if DEDUPE_ACROSS_SECTIONS:
            chosen = [e for e in chosen if e["name"] not in seen]
            seen.update(e["name"] for e in chosen)
        out[comp] = chosen
    return out


def first_sentences(text: str, n: int = 2) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:n]).strip()


def summary_of(e: dict) -> str:
    """§4: why_it_matters if present, else the first 1-2 sentences of Notes."""
    if e["why_it_matters"]:
        return e["why_it_matters"]
    if e["notes"]:
        return first_sentences(e["notes"], 2)
    return ""


# --------------------------------------------------------------------------- #
# Rendering (§5)
# --------------------------------------------------------------------------- #

def monday_of_this_week() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


def meta_line(e: dict) -> str:
    bits = [b for b in (e["state"], e["activity_type"], e["gov_actor"]) if b]
    return " · ".join(bits)


def render_text(sections: dict[str, list[dict]], total: int, monday: date) -> str:
    lines = [f"State Activity Digest — week of {monday.strftime('%b %-d, %Y')}",
             f"{total} events", "",
             INTRO, ""]
    for comp in COMPETENCIES:
        lines.append(f"== {COMPETENCY_LABELS[comp]} ==")
        evs = sections[comp]
        if not evs:
            lines.append("Nothing notable last week.")
            lines.append("")
            continue
        for e in evs:
            dots = "●" * e["relevance"]
            title = re.sub(r"^[A-Z]{2} — ", "", e["name"])
            lines.append(f"- {title}  {dots}")
            s = summary_of(e)
            if s:
                lines.append(f"  {s}")
            ml = meta_line(e)
            if ml:
                lines.append(f"  {ml}")
            for i, u in enumerate(e["source_urls"]):
                label = e["source_outlets"][i] if i < len(e["source_outlets"]) else u
                lines.append(f"  {label}: {u}")
            lines.append("")
    lines.append(f"See the full tracker: {TRACKER_URL}")
    return "\n".join(lines).rstrip() + "\n"


def render_html(sections: dict[str, list[dict]], total: int, monday: date) -> str:
    wrap = ("font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,"
            "Helvetica,Arial,sans-serif;color:#0f172a;max-width:640px;"
            "margin:0 auto;padding:8px 4px;")
    out = [f'<div style="{wrap}">']
    out.append(f'<h1 style="font-size:20px;margin:0 0 2px;">State Activity Digest</h1>')
    out.append(f'<p style="color:#64748b;font-size:13px;margin:0 0 14px;">'
               f'Week of {monday.strftime("%b %-d, %Y")} · {total} '
               f'event{"" if total == 1 else "s"}</p>')
    out.append(f'<p style="font-size:14px;color:#334155;line-height:1.5;margin:0 0 18px;">'
               f'{escape(INTRO)}</p>')

    for comp in COMPETENCIES:
        out.append(f'<h2 style="font-size:15px;border-bottom:2px solid #e2e8f0;'
                   f'padding-bottom:4px;margin:22px 0 10px;">'
                   f'{COMPETENCY_LABELS[comp]}</h2>')
        evs = sections[comp]
        if not evs:
            out.append('<p style="color:#94a3b8;font-size:13px;margin:0;">'
                       'Nothing notable last week.</p>')
            continue
        for e in evs:
            title = escape(re.sub(r"^[A-Z]{2} — ", "", e["name"]))
            first_url = e["source_urls"][0] if e["source_urls"] else ""
            title_html = (f'<a href="{escape(first_url)}" style="color:#0f172a;'
                          f'text-decoration:none;">{title}</a>' if first_url else title)
            dots = "●" * e["relevance"]
            out.append('<div style="margin:0 0 16px;">')
            out.append(f'<div style="font-weight:700;font-size:14px;">{title_html} '
                       f'<span style="color:#f59e0b;font-size:11px;">{dots}</span></div>')
            s = summary_of(e)
            if s:
                out.append(f'<div style="font-size:13px;color:#334155;line-height:1.5;'
                           f'margin:3px 0;">{escape(s)}</div>')
            ml = meta_line(e)
            if ml:
                out.append(f'<div style="font-size:12px;color:#64748b;">{escape(ml)}</div>')
            links = []
            for i, u in enumerate(e["source_urls"]):
                label = e["source_outlets"][i] if i < len(e["source_outlets"]) else u
                links.append(f'<a href="{escape(u)}" style="color:#2563eb;'
                             f'text-decoration:none;">{escape(label)}</a>')
            if links:
                out.append(f'<div style="font-size:12px;margin-top:2px;">'
                           f'{" · ".join(links)}</div>')
            out.append('</div>')
    out.append(f'<p style="border-top:1px solid #e2e8f0;margin-top:24px;'
               f'padding-top:12px;font-size:13px;">'
               f'<a href="{escape(TRACKER_URL)}" style="color:#2563eb;'
               f'text-decoration:none;font-weight:600;">See the full tracker →</a></p>')
    out.append('</div>')
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Sending (§6)
# --------------------------------------------------------------------------- #

def get_recipients(override: str | None) -> list[str]:
    """The only thing a subscriber model changes later. §0: keep RECIPIENTS as-is."""
    if override:
        return [override]
    return RECIPIENTS


def send_email(subject: str, html: str, text: str, recipients: list[str]) -> None:
    if not RESEND_API_KEY:
        sys.exit("Missing RESEND_API_KEY; see digest_feature_brief.md §6.")
    payload = {
        "from": DIGEST_FROM,
        "to": recipients,
        "subject": subject,
        "html": html,
        "text": text,
    }
    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}",
                 "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if not (200 <= resp.status_code < 300):
        # §0/§6: surface the full Resend error (a 403 here usually means the
        # recipient isn't the Resend account address pre-DNS-verification).
        raise RuntimeError(
            f"Resend send failed: HTTP {resp.status_code} — {resp.text}"
        )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser(description="Send the weekly state-capacity email digest.")
    ap.add_argument("--days", type=int, default=7, help="Digest window (default 7).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Render + per-category counts to stdout; send nothing.")
    ap.add_argument("--to", default=None, help="Override recipient (post-DNS only).")
    args = ap.parse_args()

    events = load_events(args.days)
    sections = select_all(events)
    total = len({e["name"] for evs in sections.values() for e in evs})
    monday = monday_of_this_week()
    subject = f"State Activity Digest — week of {monday.strftime('%b %-d, %Y')}: {total} events"

    html = render_html(sections, total, monday)
    text = render_text(sections, total, monday)

    if args.dry_run:
        print(f"Window: last {args.days} days · {len(events)} events in window")
        print(f"Subject: {subject}\n")
        for comp in COMPETENCIES:
            evs = sections[comp]
            n3 = sum(1 for e in evs if e["relevance"] == 3)
            n2 = sum(1 for e in evs if e["relevance"] == 2)
            print(f"[{COMPETENCY_LABELS[comp]}] {len(evs)} selected ({n3}×●●● + {n2}×●●)")
            for e in evs:
                title = re.sub(r"^[A-Z]{2} — ", "", e["name"])
                print(f"    {'●' * e['relevance']:<3} {e['state']:<3} {title}")
            if not evs:
                print("    (nothing notable last week)")
            print()
        print("--- dry run: no email sent ---")
        return

    recipients = get_recipients(args.to)
    send_email(subject, html, text, recipients)
    print(f"Sent digest ({total} events) to {', '.join(recipients)} from {DIGEST_FROM}")


if __name__ == "__main__":
    main()
