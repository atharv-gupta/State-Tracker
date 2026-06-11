"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import usa from "@svg-maps/usa";
import Header from "./header";

const STATE_NAMES = Object.fromEntries(usa.locations.map((l) => [l.id.toUpperCase(), l.name]));

const PILLARS = [
  { key: "procedure", label: "Procedure", color: "#d97706" },
  { key: "digital", label: "Digital", color: "#2563eb" },
  { key: "civil-service", label: "Civil service", color: "#059669" },
];
const PILLAR_COLOR = Object.fromEntries(PILLARS.map((p) => [p.key, p.color]));

const TIME_WINDOWS = [
  { key: "week", label: "Week", days: 7 },
  { key: "month", label: "Month", days: 31 },
  { key: "all", label: "All", days: null },
];

const PAGE_SIZE = 10;

// e.g. 1 … 4 5 6 … 12 — full list when it's short
function pagesToShow(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const wanted = [...new Set([1, current - 1, current, current + 1, total])]
    .filter((p) => p >= 1 && p <= total)
    .sort((a, b) => a - b);
  const out = [];
  let prev = 0;
  for (const p of wanted) {
    if (p - prev > 1) out.push("…");
    out.push(p);
    prev = p;
  }
  return out;
}

function cutoffFor(key) {
  const w = TIME_WINDOWS.find((t) => t.key === key);
  if (!w || !w.days) return null;
  const d = new Date();
  d.setDate(d.getDate() - w.days);
  return d.toISOString().slice(0, 10);
}

export default function Home() {
  const [events, setEvents] = useState(null);
  const [error, setError] = useState(null);
  const [stateFilter, setStateFilter] = useState(null);
  const [pillarFilter, setPillarFilter] = useState(new Set());
  const [activityFilter, setActivityFilter] = useState("");
  const [actorFilter, setActorFilter] = useState("");
  const [timeFilter, setTimeFilter] = useState("week");
  const [hovered, setHovered] = useState(null);
  const [page, setPage] = useState(1);
  const listRef = useRef(null);

  useEffect(() => {
    setPage(1);
  }, [stateFilter, pillarFilter, activityFilter, actorFilter, timeFilter]);

  useEffect(() => {
    fetch("/api/events")
      .then((r) => r.json())
      .then((d) => (d.error ? setError(d.error) : setEvents(d.events)))
      .catch((e) => setError(String(e)));
  }, []);

  const activityTypes = useMemo(
    () => [...new Set((events || []).map((e) => e.activity_type).filter(Boolean))].sort(),
    [events]
  );
  const actorTypes = useMemo(
    () => [...new Set((events || []).map((e) => e.actor_type).filter(Boolean))].sort(),
    [events]
  );

  // Everything except the state filter — drives both map shading and the list
  const baseFiltered = useMemo(() => {
    if (!events) return [];
    const cutoff = cutoffFor(timeFilter);
    return events.filter((e) => {
      if (cutoff && (!e.date || e.date < cutoff)) return false;
      if (pillarFilter.size && !e.pillars.some((p) => pillarFilter.has(p))) return false;
      if (activityFilter && e.activity_type !== activityFilter) return false;
      if (actorFilter && e.actor_type !== actorFilter) return false;
      return true;
    });
  }, [events, pillarFilter, activityFilter, actorFilter, timeFilter]);

  const countsByState = useMemo(() => {
    const c = {};
    for (const e of baseFiltered) c[e.state] = (c[e.state] || 0) + 1;
    return c;
  }, [baseFiltered]);

  const shown = useMemo(
    () => (stateFilter ? baseFiltered.filter((e) => e.state === stateFilter) : baseFiltered),
    [baseFiltered, stateFilter]
  );

  const totalPages = Math.max(1, Math.ceil(shown.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageItems = shown.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  const goTo = (n) => {
    setPage(n);
    listRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const maxCount = Math.max(1, ...Object.values(countsByState));
  const fillFor = (code) => {
    const n = countsByState[code] || 0;
    if (!n) return "#e8edf2";
    const t = n / maxCount;
    const alpha = 0.25 + 0.75 * t;
    return `rgba(37, 99, 235, ${alpha.toFixed(2)})`;
  };

  const togglePillar = (key) => {
    const next = new Set(pillarFilter);
    next.has(key) ? next.delete(key) : next.add(key);
    setPillarFilter(next);
  };

  const clearAll = () => {
    setStateFilter(null);
    setPillarFilter(new Set());
    setActivityFilter("");
    setActorFilter("");
    setTimeFilter("week");
  };

  const hasFilters =
    stateFilter || pillarFilter.size || activityFilter || actorFilter || timeFilter !== "week";

  return (
    <main className="wrap">
      <Header active="map" />

      <section className="top">
        <div className="mapcard">
          <svg viewBox={usa.viewBox} role="img" aria-label="US map of events">
            {usa.locations.map((loc) => {
              const code = loc.id.toUpperCase();
              const selected = stateFilter === code;
              return (
                <path
                  key={loc.id}
                  d={loc.path}
                  className={`state ${selected ? "selected" : ""}`}
                  fill={selected ? "#1e3a8a" : fillFor(code)}
                  onClick={() => setStateFilter(selected ? null : code)}
                  onMouseEnter={() => setHovered(code)}
                  onMouseLeave={() => setHovered(null)}
                >
                  <title>{`${loc.name}: ${countsByState[code] || 0} event${(countsByState[code] || 0) === 1 ? "" : "s"}`}</title>
                </path>
              );
            })}
          </svg>
          <div className="maplegend">
            {hovered ? (
              <span>
                <strong>{STATE_NAMES[hovered]}</strong> — {countsByState[hovered] || 0} event
                {(countsByState[hovered] || 0) === 1 ? "" : "s"} · click to filter
              </span>
            ) : (
              <span>Darker = more events · click a state to filter</span>
            )}
          </div>
        </div>

        <aside className="panel">
          <div className="panelrow">
            <label>Time window</label>
            <div className="timebtns">
              {TIME_WINDOWS.map((t) => (
                <button
                  key={t.key}
                  className={`timebtn ${timeFilter === t.key ? "on" : ""}`}
                  onClick={() => setTimeFilter(t.key)}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          <div className="panelrow">
            <label>Pillars</label>
            <div className="pillarbtns">
              {PILLARS.map((p) => (
                <button
                  key={p.key}
                  className={`pill ${pillarFilter.has(p.key) ? "on" : ""}`}
                  style={{ "--c": p.color }}
                  onClick={() => togglePillar(p.key)}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="panelrow">
            <label>Activity type</label>
            <select value={activityFilter} onChange={(e) => setActivityFilter(e.target.value)}>
              <option value="">All</option>
              {activityTypes.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div className="panelrow">
            <label>Government actor</label>
            <select value={actorFilter} onChange={(e) => setActorFilter(e.target.value)}>
              <option value="">All</option>
              {actorTypes.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div className="panelfoot">
            <span className="count">
              {events ? `${shown.length} event${shown.length === 1 ? "" : "s"}` : "Loading…"}
              {stateFilter ? ` · ${STATE_NAMES[stateFilter] || stateFilter}` : ""}
            </span>
            {hasFilters ? (
              <button className="clear" onClick={clearAll}>
                Reset
              </button>
            ) : null}
          </div>
        </aside>
      </section>

      {error ? <p className="error">Error loading events: {error}</p> : null}

      <section className="list" ref={listRef}>
        {pageItems.map((e) => (
          <article key={e.id} className="card">
            <div className="cardtop">
              <span className="statechip">{e.state}</span>
              <time>{e.date}</time>
              {e.activity_type ? <span className="chip">{e.activity_type}</span> : null}
              {e.actor_type ? <span className="chip actor">{e.actor_type}</span> : null}
              {e.pillars.map((p) => (
                <span key={p} className="chip pillar" style={{ "--c": PILLAR_COLOR[p] || "#64748b" }}>
                  {p}
                </span>
              ))}
              {e.significance ? <span className="sig">{"●".repeat(e.significance)}</span> : null}
            </div>
            <h2>{e.name.replace(/^[A-Z]{2} — /, "")}</h2>
            {e.notes ? <p className="notes">{e.notes}</p> : null}
            <div className="cardfoot">
              {e.gov_actor ? <span className="actor-name">{e.gov_actor}</span> : null}
              <span className="links">
                {e.urls.map((u, i) => (
                  <a key={u} href={u} target="_blank" rel="noreferrer">
                    {e.outlets[i] || new URL(u).hostname.replace(/^www\./, "")}
                  </a>
                ))}
              </span>
              {e.article_count > 1 ? <span className="merged">{e.article_count} articles merged</span> : null}
            </div>
          </article>
        ))}
        {events && !shown.length ? <p className="empty">No events match these filters.</p> : null}
      </section>

      {totalPages > 1 ? (
        <nav className="pager" aria-label="Event list pages">
          <button className="pagebtn" disabled={safePage === 1} onClick={() => goTo(safePage - 1)}>
            ← Prev
          </button>
          {pagesToShow(safePage, totalPages).map((p, i) =>
            p === "…" ? (
              <span key={`gap${i}`} className="pagegap">
                …
              </span>
            ) : (
              <button
                key={p}
                className={`pagebtn num ${p === safePage ? "on" : ""}`}
                onClick={() => goTo(p)}
              >
                {p}
              </button>
            )
          )}
          <button
            className="pagebtn"
            disabled={safePage === totalPages}
            onClick={() => goTo(safePage + 1)}
          >
            Next →
          </button>
          <span className="pageinfo">
            {(safePage - 1) * PAGE_SIZE + 1}–{Math.min(safePage * PAGE_SIZE, shown.length)} of{" "}
            {shown.length}
          </span>
        </nav>
      ) : null}
    </main>
  );
}
