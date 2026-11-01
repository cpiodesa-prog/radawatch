#!/usr/bin/env python3
"""RadaWatch entry point: run the monitoring pipeline."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radawatch.config import Config
from radawatch.pipeline import Pipeline
from radawatch.state import StateManager
from radawatch.collectors import COLLECTOR_REGISTRY

# Auto-discover collectors by importing subpackages
import radawatch.collectors.odesa  # noqa: F401
import radawatch.collectors.mykolaiv  # noqa: F401
import radawatch.collectors.kherson  # noqa: F401
import radawatch.collectors.nazk  # noqa: F401

from radawatch.analyzers.risk_keywords import RiskKeywordsAnalyzer
from radawatch.analyzers.youtube_compliance import YoutubeComplianceAnalyzer
from radawatch.analyzers.newsworthiness import NewsworthinessAnalyzer
from radawatch.verifiers.dedup import DedupVerifier
from radawatch.verifiers.cross_reference import CrossReferenceVerifier
from radawatch.intelligence.person_dossier import (
    PersonDossierBuilder, format_dossier_telegram,
    format_document_diff_telegram, format_decision_analysis_telegram,
)
from radawatch.intelligence.decision_analyzer import DecisionAnalyzer
from radawatch.intelligence.document_tracker import DocumentTracker
from radawatch.drafters.telegram_formatter import format_event
from radawatch.drafters.infoprivid import format_digest
from radawatch.publishers.telegram import TelegramPublisher
from radawatch.analyzers.noise_filter import NoiseFilter


def main():
    parser = argparse.ArgumentParser(description="RadaWatch monitoring pipeline")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    parser.add_argument("--filter", type=str, nargs="*", default=None,
                        help="Collector groups to run: council, risk_analysis, declarations")
    parser.add_argument("--dry-run", action="store_true", help="Collect and analyze without publishing or saving state")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    config = Config(data=None) if args.config is None else Config(data=None)
    state = StateManager()
    pipeline = Pipeline(config, state)

    # Register all discovered collectors
    for source_id, cls in sorted(COLLECTOR_REGISTRY.items()):
        cfg = config.collectors.get(source_id, {})
        if cfg.get("enabled", True):
            pipeline.register_collector(cls(config, state))
            logging.getLogger("radawatch").debug("Registered collector: %s", source_id)

    # Register analyzers
    pipeline.register_analyzer(RiskKeywordsAnalyzer(config))
    pipeline.register_analyzer(YoutubeComplianceAnalyzer(config))
    pipeline.register_analyzer(NewsworthinessAnalyzer(config))

    # Register verifiers
    pipeline.register_verifier(DedupVerifier(config, state))
    pipeline.register_verifier(CrossReferenceVerifier(config, state))

    # Register intelligence layer
    pipeline._intelligence.append(PersonDossierBuilder(config, state))
    pipeline._intelligence.append(DecisionAnalyzer(config, state))
    pipeline._intelligence.append(DocumentTracker(config, state))

    results = pipeline.run(collector_filter=args.filter, dry_run=args.dry_run)

    # In dry-run, print formatted Telegram messages for each event
    if args.dry_run:
        for event in results["events"]:
            msg = format_event(event)
            if msg:
                print("----")
                print(msg)
    else:
        _send_telegram_notifications(results["events"], state)
        _send_intelligence_alerts(results["events"])
        _send_infoprivid_digest(results.get("infoprivids", []), results["events"])

    n_events = len(results["events"])
    n_errors = len(results["errors"])
    print(f"\nDone: {n_events} new events, {len(results['drafts'])} drafts, {n_errors} errors.")
    print(f"Registered collectors: {len(COLLECTOR_REGISTRY)}")

    if n_errors:
        for err in results["errors"]:
            print(f"  [{err['stage']}] {err['source']}: {err['error']}")

    fatal_errors = [e for e in results["errors"] if "timeout" not in e.get("error", "")]
    return 1 if fatal_errors else 0


def _send_telegram_notifications(events: list, state=None):
    """Send each event to the appropriate Telegram chat based on city/source."""
    import os

    chat_map = {
        "odesa": os.environ.get("TELEGRAM_CHAT_ODESA", ""),
        "mykolaiv": os.environ.get("TELEGRAM_CHAT_MYKOLAIV", ""),
        "kherson": os.environ.get("TELEGRAM_CHAT_KHERSON", ""),
    }
    declarations_chat = os.environ.get("TELEGRAM_CHAT_DECLARATIONS", "")

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return

    tg = TelegramPublisher(token=token)
    noise = NoiseFilter(state=state)
    sent = 0
    filtered = 0

    for event in events:
        if noise.is_noise(event):
            filtered += 1
            continue

        msg = format_event(event)
        if not msg:
            continue

        if event.source.startswith("nazk."):
            chat_id = declarations_chat
        else:
            chat_id = chat_map.get(event.city, "")

        if chat_id:
            if tg.send(msg, chat_id=chat_id):
                sent += 1

    log = logging.getLogger("radawatch")
    if sent:
        log.info("Sent %d Telegram notifications", sent)
    if filtered:
        log.info("Filtered %d routine land permits (noise)", filtered)


def _send_intelligence_alerts(events: list):
    import os

    editor_chat = os.environ.get("EDITOR_CHAT_ID", "")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token or not editor_chat:
        return

    chat_map = {
        "odesa": os.environ.get("TELEGRAM_CHAT_ODESA", ""),
        "mykolaiv": os.environ.get("TELEGRAM_CHAT_MYKOLAIV", ""),
        "kherson": os.environ.get("TELEGRAM_CHAT_KHERSON", ""),
    }

    tg = TelegramPublisher(token=token)
    sent = 0

    for event in events:
        dossier = event.data.get("dossier")
        if dossier:
            msg = format_dossier_telegram(dossier)
            if tg.send(msg, chat_id=editor_chat, disable_preview=True):
                sent += 1

        diff_msg = format_document_diff_telegram(event)
        if diff_msg:
            city_chat = chat_map.get(event.city, "")
            if city_chat:
                tg.send(diff_msg, chat_id=city_chat, disable_preview=True)
            if tg.send(diff_msg, chat_id=editor_chat, disable_preview=True):
                sent += 1

        analysis_msg = format_decision_analysis_telegram(event)
        if analysis_msg:
            if tg.send(analysis_msg, chat_id=editor_chat, disable_preview=True):
                sent += 1

    if sent:
        logging.getLogger("radawatch").info("Sent %d intelligence alerts", sent)


def _send_infoprivid_digest(infoprivids: list, events: list):
    import os

    if not infoprivids:
        return

    editor_chat = os.environ.get("EDITOR_CHAT_ID", "")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token or not editor_chat:
        return

    digest = format_digest(infoprivids, events)
    tg = TelegramPublisher(token=token)
    if tg.send(digest, chat_id=editor_chat, disable_preview=True):
        logging.getLogger("radawatch").info("Sent infoprivid digest (%d items) to editor", len(infoprivids))


if __name__ == "__main__":
    sys.exit(main())
