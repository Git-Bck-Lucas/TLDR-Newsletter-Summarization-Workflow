"""Scraper für das öffentliche TLDR-Web-Archiv (tldr.tech).

Struktur einer Ausgabe (verifiziert):
- Jede Kategorie ist ein <section> mit <header><h3>Kategoriename</h3>.
- Jedes Item ist ein <article> mit:
    - <a class="font-bold" href="ZIEL-URL"><h3>Titel (x minute read)</h3></a>
    - <div class="newsletter-html">Kurzzusammenfassung</div>
- Ads/Sponsored: Anker trägt rel="...nofollow" oder es fehlt das div.newsletter-html.
- Ausgehende Links sind direkte Ziel-URLs mit nur einem utm_*-Parameter.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import requests
from bs4 import BeautifulSoup

from .models import Issue, Item

BASE = "https://tldr.tech"
NEWSLETTERS = ("ai", "data")

# Realistischer User-Agent; TLDRs robots.txt erlaubt /ai und /data.
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; tldr-digest/1.0)"}

# Lesezeit im Titel, z.B. "(5 minute read)"
_READING_TIME_RE = re.compile(r"\s*\((\d+\s+minute\s+read)\)\s*$", re.IGNORECASE)
# Sponsored-Item: Titel endet auf "(Sponsor)". Einziges verlässliches Ad-Signal
# (rel ist nur noopener/noreferrer, newsletter-html ist vorhanden).
_SPONSOR_RE = re.compile(r"\(sponsor\)\s*$", re.IGNORECASE)


def _get(url: str) -> str:
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text


def _clean_url(url: str) -> str:
    """Entfernt utm_*-Tracking-Parameter, behält den Rest der URL bei."""
    parts = urlparse(url)
    kept = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_")]
    return urlunparse(parts._replace(query=urlencode(kept)))


def _parse_items(html: str) -> list[Item]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[Item] = []

    for section in soup.select("section"):
        header = section.find("header")
        category = header.get_text(strip=True) if header else ""

        for article in section.select("article"):
            anchor = article.select_one("a.font-bold[href]")
            summary_div = article.select_one("div.newsletter-html")

            # Redaktionelles Item braucht Anker + Summary.
            if anchor is None or summary_div is None:
                continue

            raw_title = anchor.get_text(strip=True)
            # Ads raus: Titel endet auf "(Sponsor)".
            if _SPONSOR_RE.search(raw_title):
                continue

            reading_time = None
            m = _READING_TIME_RE.search(raw_title)
            if m:
                reading_time = m.group(1)
                raw_title = _READING_TIME_RE.sub("", raw_title)

            items.append(
                Item(
                    section=category,
                    title=raw_title.strip(),
                    url=_clean_url(anchor["href"]),
                    summary=summary_div.get_text(strip=True),
                    reading_time=reading_time,
                )
            )

    return items


def fetch_issue(newsletter: str, issue_date: str) -> Issue | None:
    """Holt und parst eine Ausgabe. None, wenn keine echte Ausgabe (Landingpage).

    Ein nicht existierendes Datum liefert HTTP 200 mit Signup-Landingpage,
    nicht 404 -> deshalb prüfen wir, ob überhaupt Items geparst wurden.
    """
    html = _get(f"{BASE}/{newsletter}/{issue_date}")
    items = _parse_items(html)
    if not items:
        return None
    return Issue(newsletter=newsletter, date=issue_date, items=items)


def find_latest_issue(
    newsletter: str,
    today: date | None = None,
    max_lookback: int = 7,
) -> Issue | None:
    """Neueste echte Ausgabe, indem Daten von heute rückwärts geprobt werden.

    Der /archives-Index ist veraltet und deshalb unbrauchbar. Stattdessen rufen
    wir /{newsletter}/{date} direkt ab; eine nicht existierende Ausgabe liefert die
    Landingpage (keine Items) -> None. Der erste Treffer ist die neueste Ausgabe.
    max_lookback deckt Wochenenden und den Mo/Do-Rhythmus von TLDR Data ab.
    """
    today = today or date.today()
    for delta in range(max_lookback + 1):
        d = (today - timedelta(days=delta)).isoformat()
        issue = fetch_issue(newsletter, d)
        if issue:
            return issue
    return None


if __name__ == "__main__":
    # Manueller Smoke-Test: neueste Ausgabe je Sektion holen und anzeigen.
    for nl in NEWSLETTERS:
        issue = find_latest_issue(nl)
        if issue is None:
            print(f"[{nl}] keine Ausgabe in den letzten Tagen gefunden")
            continue
        print(f"[{nl}] neueste Ausgabe: {issue.date} ({len(issue.items)} Items)")
        for it in issue.items[:3]:
            rt = f" [{it.reading_time}]" if it.reading_time else ""
            print(f"  - ({it.section}) {it.title}{rt} -> {it.url}")
