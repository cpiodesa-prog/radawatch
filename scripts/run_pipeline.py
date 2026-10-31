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
from radawatch.intelligence.person_dossier import PersonDossierBuilder
from radawatch.intelligence.decision_analyzer import DecisionAnalyzer
from radawatch.intelligence.document_tracker import DocumentTracker
from radawatch.drafters.telegram_formatter import format_event
from radawatch.publishers.telegram import TelegramPublisher


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

    n_events = len(results["events"])
    n_errors = len(results["errors"])
    print(f"\nDone: {n_events} new events, {len(results['drafts'])} drafts, {n_errors} errors.")
    print(f"Registered collectors: {len(COLLECTOR_REGISTRY)}")

    if n_errors:
        for err in results["errors"]:
            print(f"  [{err['stage']}] {err['source']}: {err['error']}")

    return 1 if n_errors else 0


if __name__ == "__main__":
    sys.exit(main())
