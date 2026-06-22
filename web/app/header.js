import Link from "next/link";

export default function Header({ active }) {
  return (
    <header className="head">
      <h1>State Activity Tracker</h1>
      <p className="sub">What state governments are actually doing, in RAF&apos;s capacities</p>
      <nav className="tabs">
        <Link href="/" className={`tab ${active === "map" ? "on" : ""}`}>
          Map
        </Link>
        <Link href="/methodology" className={`tab ${active === "methodology" ? "on" : ""}`}>
          Sources &amp; methodology
        </Link>
      </nav>
    </header>
  );
}
