"""Orchestrierung: neue Ausgaben holen, Digest bauen, Mail senden, State aktualisieren.

Aufruf:
  python -m tldr_digest.main            # echter Lauf: baut Digest und verschickt Mail
  python -m tldr_digest.main --dry-run  # baut Digest, schreibt HTML in Datei, kein Versand
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

from . import agent, mailer
from .config import load_settings
from .models import Issue
from .scraper import NEWSLETTERS, find_latest_issue
from .state import load_state, save_state

logger = logging.getLogger(__name__)

_DRY_RUN_OUT = Path(__file__).resolve().parent.parent / "dry_run.html"


def _collect_new_issues(state: dict[str, str]) -> list[Issue]:
    """Je Sektion die neueste Ausgabe holen und überspringen, wenn schon verschickt."""
    new: list[Issue] = []
    for nl in NEWSLETTERS:
        issue = find_latest_issue(nl)
        if issue is None:
            logger.info("[%s] keine aktuelle Ausgabe gefunden", nl)
            continue
        if state.get(nl) == issue.date:
            logger.info("[%s] Ausgabe %s bereits verschickt, überspringe", nl, issue.date)
            continue
        logger.info("[%s] neue Ausgabe %s (%d Items)", nl, issue.date, len(issue.items))
        new.append(issue)
    return new


def _subject(issues: list[Issue]) -> str:
    return f"Dein Tech, Data & AI Update – {date.today().isoformat()}"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Digest bauen und als HTML-Datei speichern, statt eine Mail zu senden.",
    )
    args = parser.parse_args()

    settings = load_settings()
    state = load_state()

    issues = _collect_new_issues(state)
    if not issues:
        logger.info("Nichts Neues. Kein Versand.")
        return

    logger.info("Baue Digest aus %d Ausgabe(n) ...", len(issues))
    html = agent.run(issues, settings)

    if args.dry_run:
        _DRY_RUN_OUT.write_text(html, encoding="utf-8")
        logger.info("Dry-Run: HTML geschrieben nach %s (kein Versand, kein State-Update)",
                    _DRY_RUN_OUT)
        return

    if not settings.smtp_user or not settings.smtp_app_password:
        raise SystemExit("SMTP_USER und SMTP_APP_PASSWORD müssen für den Versand gesetzt sein.")

    mailer.send(html, _subject(issues), settings)
    logger.info("Mail verschickt an %s", settings.mail_to)

    for issue in issues:
        state[issue.newsletter] = issue.date
    save_state(state)
    logger.info("State aktualisiert: %s", state)


if __name__ == "__main__":
    main()
