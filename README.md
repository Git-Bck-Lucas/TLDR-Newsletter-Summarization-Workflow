# TLDR Newsletter Digest

Ein täglicher Mini-Agent, der die Newsletter **TLDR AI** und **TLDR Data** aus dem
öffentlichen TLDR-Web-Archiv zieht, auf mich zugeschnitten in deutschem Fließtext
zusammenfasst und mir das Ergebnis als HTML-Mail schickt.

Der Agent bekommt ein `fetch_url`-Tool und liest bei relevanten Themen den Originalartikel
nach, statt sich mit der kurzen TLDR-Kurzfassung zu begnügen. Das eigenständige Entscheiden,
welchen Links er folgt, ist die agentische Komponente. Alles andere (Scrapen, Mailversand,
Scheduling) ist bewusst deterministische Pipeline ohne AI.

## Architektur
```
tldr_digest/
  config.py    pydantic-settings (Secrets aus der Umgebung)
  scraper.py   TLDR-Archiv -> geparste Items (requests + BeautifulSoup)
  models.py    Item / Issue (Pydantic)
  tools.py     fetch_url-Tool (Schema + Implementierung)
  agent.py     handgeschriebene Anthropic-Tool-Use-Loop -> fertiges HTML
  mailer.py    Gmail-SMTP-Versand
  state.py     state.json: zuletzt verschicktes Datum je Sektion (Idempotenz)
  main.py      Orchestrierung
profile.md     Interessen-/Stil-Steckbrief, fließt in den System-Prompt
```

## Lokal ausführen
```bash
python -m venv .venv
./.venv/bin/pip install -r requirements.txt
```
Umgebungsvariablen (lokal via `.env`, siehe `.env.example`):
`ANTHROPIC_API_KEY`, `SMTP_USER`, `SMTP_APP_PASSWORD`, `MAIL_TO`.

```bash
# Digest bauen und als dry_run.html speichern (kein Mailversand, nur ANTHROPIC_API_KEY nötig):
./.venv/bin/python -m tldr_digest.main --dry-run

# Echter Lauf (baut Digest und verschickt Mail):
./.venv/bin/python -m tldr_digest.main
```

`SMTP_APP_PASSWORD` ist ein Gmail-**App-Passwort**, nicht das normale Passwort.

## Deployment
Läuft täglich über GitHub Actions (`.github/workflows/daily.yml`), kein eigener Server nötig.
Die vier Werte oben als **GitHub Secrets** hinterlegen. `state.json` wird vom Actions-Lauf
zurück committet, damit dieselbe Ausgabe nicht doppelt verschickt wird.

**Uhrzeit/DST:** Der Cron läuft `0 5 * * *` in UTC, also 07:00 Berlin im Sommer (CEST) und
06:00 im Winter (CET). Bewusst so gehalten, kein DST-Handling.

## Datenquelle
`https://tldr.tech/{ai,data}/YYYY-MM-DD`, server-side gerendert. Die neueste Ausgabe wird
durch Proben der Daten von heute rückwärts gefunden (der Archiv-Index ist veraltet). TLDR AI
erscheint werktags, TLDR Data nur Montag und Donnerstag; ein Datum ohne Ausgabe liefert eine
Landingpage statt 404, was am Fehlen von `<article>`-Items erkannt wird.
