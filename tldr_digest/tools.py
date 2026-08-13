"""Das fetch_url-Tool: holt einen Original-Artikel und gibt gekürzten Klartext zurück.

Zwei Teile:
- FETCH_URL_TOOL: das Tool-Schema, das der Anthropic-API mitgegeben wird (so weiß das
  Modell, dass es das Tool gibt und wie es aufgerufen wird).
- fetch_url(): die tatsächliche Implementierung, die UNSER Code ausführt, wenn das Modell
  das Tool aufruft. Das Modell führt nichts selbst aus, es fragt nur an.
"""

from __future__ import annotations

from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; tldr-digest/1.0)"}
_TIMEOUT = 10           # Sekunden
_MAX_BYTES = 2_000_000  # 2 MB Download-Deckel, bevor geparst wird

# Tool-Definition für die Anthropic-Messages-API.
FETCH_URL_TOOL = {
    "name": "fetch_url",
    "description": (
        "Holt den Volltext des Original-Artikels hinter einer der URLs aus der Item-Liste "
        "und gibt ihn als gekürzten Klartext zurück. Nutze das Tool gezielt nur für Items, "
        "die für Lucas wirklich relevant sind und bei denen die kurze TLDR-Zusammenfassung "
        "zu dünn ist, um echten Mehrwert zu liefern. Das Aufruf-Budget ist begrenzt, geh "
        "also sparsam damit um."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Die Artikel-URL, exakt aus der Item-Liste übernommen.",
            }
        },
        "required": ["url"],
    },
}


def fetch_url(url: str, char_cap: int) -> str:
    """Lädt eine http(s)-Seite, strippt HTML zu Klartext, kürzt auf char_cap Zeichen.

    Gibt bei Problemen einen kurzen Fehlertext zurück (kein Exception-Throw), damit die
    Agent-Loop weiterlaufen kann. Das Modell sieht den Fehler als Tool-Ergebnis und
    kann darauf reagieren.
    """
    parts = urlparse(url)
    if parts.scheme not in ("http", "https"):
        return f"Fehler: nur http/https erlaubt, nicht '{parts.scheme}'."

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT, stream=True)
        resp.raise_for_status()

        ctype = resp.headers.get("content-type", "")
        if "html" not in ctype and "text" not in ctype:
            return f"Fehler: kein Text/HTML-Inhalt ({ctype!r})."

        # Download deckeln, damit ein Riesen-Dokument nicht alles sprengt.
        chunks: list[bytes] = []
        total = 0
        for chunk in resp.iter_content(chunk_size=16384):
            chunks.append(chunk)
            total += len(chunk)
            if total >= _MAX_BYTES:
                break
        html = b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")
    except requests.RequestException as e:
        return f"Fehler beim Laden: {e}"

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)

    if len(text) > char_cap:
        text = text[:char_cap] + "\n[... gekürzt ...]"
    return text
