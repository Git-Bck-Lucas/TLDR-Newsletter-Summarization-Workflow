"""Der Agent: eine handgeschriebene Anthropic-Tool-Use-Loop.

Ablauf (das ist der Kern-Mechanismus, den es zu verstehen gilt):
1. Wir schicken System-Prompt + Items an das Modell und geben das fetch_url-Tool mit.
2. Antwortet das Modell mit stop_reason == "tool_use", will es Tools aufrufen. Wir führen
   sie aus (fetch_url), hängen die Ergebnisse als tool_result an und schicken erneut.
3. Das wiederholt sich, bis das Modell fertig ist (stop_reason != "tool_use"). Dann ist
   die letzte Antwort das fertige HTML-Digest.

Das Fetch-Budget zählen WIR mit, nicht das Modell: ist es erschöpft, geben wir statt eines
Artikels einen Hinweis zurück ("keine weiteren Fetches").
"""

from __future__ import annotations

import logging
from pathlib import Path

import anthropic

from .config import Settings
from .models import Issue
from .tools import FETCH_URL_TOOL, fetch_url

logger = logging.getLogger(__name__)

# profile.md liegt im Repo-Root, eine Ebene über diesem Package.
_PROFILE_PATH = Path(__file__).resolve().parent.parent / "profile.md"


def _load_profile() -> str:
    return _PROFILE_PATH.read_text(encoding="utf-8")


def _build_system_prompt(profile: str) -> str:
    return f"""Du bist Lucas' persönlicher Redakteur für Tech-, Data- und AI-News. Deine \
Aufgabe: aus den rohen TLDR-Items unten eine runde, angenehm lesbare deutsche \
Zusammenfassung schreiben, die Lucas morgens in einer Mail updatet.

Hier ist, was du über Lucas wissen musst (nutze das, um Themen zu gewichten und den Ton zu \
treffen):

{profile}

So gehst du vor:
- Die Mail muss für sich stehen. Lucas soll nach dem Lesen die Kernaussagen kennen, ohne \
einen einzigen Link anklicken zu müssen. Gib bei jedem relevanten Thema die eigentliche \
Substanz wieder: die konkreten Fakten, Zahlen, Argumente und das Fazit. Verweise der Art \
"dieser Artikel argumentiert, dass ..." sind zu wenig, erzähl stattdessen, WAS er \
argumentiert und warum das für Lucas zählt. Die Links sind nur Belege zum Vertiefen, kein \
Pflichtklick.
- Reicht dir eine TLDR-Kurzfassung nicht, um ein für Lucas relevantes Thema wirklich \
inhaltlich wiederzugeben, dann lies den Original-Artikel per fetch_url nach. Für die \
relevanten Themen ist das ausdrücklich erwünscht. Nur für Randthemen lohnt es sich nicht. \
Dein Fetch-Budget ist begrenzt, setz es also auf die wichtigsten Themen.
- Priorisiere nach Lucas' Interessen. Die relevanten Themen bekommen echten, substanziellen \
Fließtext. Randthemen fasst du am Ende knapp unter einer Überschrift "Kurz notiert" als \
kurze Liste zusammen. Reine Werbung ignorierst du.
- Lieber vollständig und substanziell als knapp. Nimm dir den Platz, den die relevanten \
Themen brauchen, die Mail darf ruhig länger werden.
- Schreibe natürliches, redigiertes Deutsch. Keine KI-Bindestriche (kein Gedankenstrich \
als Stilmittel). Fließtext statt Bullet-Wüste. Fachvokabular darf englisch bleiben.
- Verlinke bei JEDEM Thema und JEDEM Absatz die Quelle als Beleg, damit Lucas bei Interesse \
tiefer einsteigen kann. Hast du für ein Thema zusätzlich einen Original-Artikel per \
fetch_url gelesen, verlinke diesen zusätzlich zur TLDR-Quelle.

Ausgabeformat: Gib ausschließlich validen HTML-Code aus, der direkt als Mail-Body dient. \
Kein Markdown, keine ```-Codeblöcke, kein <html>/<head>/<body>-Gerüst, nur der Inhalt: \
Absätze als <p>, Themen-/Sektionsüberschriften als <h2> bzw. <h3>, Quell-Links als \
<a href="...">. Halte es schlicht, keine Inline-Styles."""


def _format_issues(issues: list[Issue]) -> str:
    """Baut die Items als kompaktes Markdown, das als User-Message reingeht."""
    lines: list[str] = []
    for issue in issues:
        nice = {"ai": "TLDR AI", "data": "TLDR Data"}.get(issue.newsletter, issue.newsletter)
        lines.append(f"# {nice} – Ausgabe {issue.date}\n")
        current_section = None
        for item in issue.items:
            if item.section != current_section:
                current_section = item.section
                lines.append(f"\n## {item.section}")
            rt = f" ({item.reading_time})" if item.reading_time else ""
            lines.append(f"\n### {item.title}{rt}")
            lines.append(f"URL: {item.url}")
            lines.append(f"TLDR: {item.summary}")
    return "\n".join(lines)


def run(issues: list[Issue], settings: Settings) -> str:
    """Führt die Agent-Loop aus und gibt das fertige HTML-Digest zurück."""
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    system = _build_system_prompt(_load_profile())

    user_message = (
        "Hier sind die heutigen TLDR-Items. Schreib daraus das deutsche HTML-Digest für "
        "Lucas.\n\n" + _format_issues(issues)
    )
    messages: list[dict] = [{"role": "user", "content": user_message}]

    fetches_used = 0
    total_in = 0
    total_out = 0
    while True:
        # Streaming, damit das (potenziell lange) Digest nicht in HTTP-Timeouts läuft;
        # get_final_message() liefert die vollständige Antwort wie bei create().
        with client.messages.stream(
            model=settings.model,
            max_tokens=20000,
            system=system,
            tools=[FETCH_URL_TOOL],
            output_config={"effort": "medium"},
            messages=messages,
        ) as stream:
            response = stream.get_final_message()

        total_in += response.usage.input_tokens
        total_out += response.usage.output_tokens

        # Fertig: keine Tool-Aufrufe mehr -> letzte Antwort ist das Digest.
        if response.stop_reason != "tool_use":
            # Sonnet-5-Preis (Standard $3/$15 pro 1M; bis 31.08.2026 Intro $2/$10).
            cost = total_in * 3 / 1e6 + total_out * 15 / 1e6
            logger.info(
                "Tokens gesamt: input=%d, output=%d, fetches=%d (~$%.3f bei Standardpreis)",
                total_in, total_out, fetches_used, cost,
            )
            return "".join(b.text for b in response.content if b.type == "text").strip()

        # Assistant-Turn (inkl. tool_use- und ggf. thinking-Blöcken) unverändert anhängen.
        messages.append({"role": "assistant", "content": response.content})

        tool_results: list[dict] = []
        for block in response.content:
            if block.type != "tool_use" or block.name != "fetch_url":
                continue
            if fetches_used >= settings.fetch_budget:
                result = (
                    "Fetch-Budget erschöpft. Ruf keine weiteren Artikel ab und schreibe "
                    "jetzt das Digest aus den vorhandenen Informationen."
                )
            else:
                fetches_used += 1
                url = block.input.get("url", "")
                logger.info("fetch_url (%d/%d): %s", fetches_used, settings.fetch_budget, url)
                result = fetch_url(url, settings.article_char_cap)
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": result}
            )

        messages.append({"role": "user", "content": tool_results})
