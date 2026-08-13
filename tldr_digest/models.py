"""Datenmodelle für eine geparste TLDR-Ausgabe."""

from __future__ import annotations

from pydantic import BaseModel


class Item(BaseModel):
    """Ein einzelnes News-Item aus einer TLDR-Ausgabe."""

    section: str          # z.B. "Headlines & Launches" (dynamisch aus dem HTML)
    title: str            # Titel ohne den "(x minute read)"-Zusatz
    url: str              # direkte Ziel-URL (utm-Parameter bereits gestrippt)
    summary: str          # die kurze TLDR-Zusammenfassung
    reading_time: str | None = None   # z.B. "5 minute read", falls vorhanden


class Issue(BaseModel):
    """Eine komplette Ausgabe einer TLDR-Sektion an einem Datum."""

    newsletter: str       # "ai" oder "data"
    date: str             # ISO-Datum "YYYY-MM-DD"
    items: list[Item]
