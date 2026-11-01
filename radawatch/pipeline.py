"""Pipeline orchestrator: collect → analyze → verify → intelligence → notify → suggest → draft → publish."""

from __future__ import annotations

import logging
import signal
import threading
from typing import Optional

from .config import Config

COLLECTOR_TIMEOUT = 300  # 5 minutes per collector
SLOW_COLLECTOR_TIMEOUT = 7200  # 2 hours for NAZK declarations (624 people, API returns 403 intermittently)
SLOW_COLLECTORS = {"nazk.declarations"}
FIRST_RUN_CAP = 50  # max new events per collector on first run (seed the rest)
from .models import Analysis, Draft, Event, Infoprivid, VerificationResult
from .state import StateManager

log = logging.getLogger("radawatch.pipeline")


class Pipeline:
    def __init__(self, config: Config, state: StateManager):
        self.config = config
        self.state = state
        self._collectors = []
        self._analyzers = []
        self._verifiers = []
        self._intelligence = []
        self._drafters = []
        self._publishers = []

    def register_collector(self, collector):
        self._collectors.append(collector)

    def register_analyzer(self, analyzer):
        self._analyzers.append(analyzer)

    def register_verifier(self, verifier):
        self._verifiers.append(verifier)

    @staticmethod
    def _run_with_timeout(fn, timeout_sec: int, label: str):
        result = []
        error = []

        def target():
            try:
                result.append(fn())
            except Exception as e:
                error.append(e)

        t = threading.Thread(target=target, daemon=True)
        t.start()
        t.join(timeout=timeout_sec)
        if t.is_alive():
            raise TimeoutError(f"{label} exceeded {timeout_sec}s")
        if error:
            raise error[0]
        return result[0] if result else []

    def register_drafter(self, drafter):
        self._drafters.append(drafter)

    def register_publisher(self, publisher):
        self._publishers.append(publisher)

    def run(
        self,
        collector_filter: Optional[list[str]] = None,
        dry_run: bool = False,
    ) -> dict:
        """Run the full pipeline. Returns summary dict."""
        results = {
            "events": [],
            "analyses": [],
            "verifications": [],
            "infoprivids": [],
            "drafts": [],
            "published": [],
            "errors": [],
        }

        # 1. COLLECT
        all_events: list[Event] = []
        for collector in self._collectors:
            src = collector.source_id
            cfg = self.config.collectors.get(src, {})
            if not cfg.get("enabled", True):
                continue
            if collector_filter and cfg.get("group") not in collector_filter:
                continue

            timeout = SLOW_COLLECTOR_TIMEOUT if src in SLOW_COLLECTORS else COLLECTOR_TIMEOUT
            log.info("Collecting from %s (timeout %ds)", src, timeout)
            try:
                events = self._run_with_timeout(collector.collect, timeout, src)
                new_events = [e for e in events if not self.state.is_seen(e.id)]
                if len(new_events) > FIRST_RUN_CAP:
                    log.warning("  %d new events — capping at %d, seeding %d as seen",
                                len(new_events), FIRST_RUN_CAP, len(new_events) - FIRST_RUN_CAP)
                    seed_events = new_events[FIRST_RUN_CAP:]
                    for e in seed_events:
                        self.state.mark_seen(e.id)
                    new_events = new_events[:FIRST_RUN_CAP]
                log.info("  %d new events (of %d total)", len(new_events), len(events))
                all_events.extend(new_events)
            except TimeoutError:
                log.error("  Collector %s timed out after %ds", src, timeout)
                results["errors"].append({"stage": "collect", "source": src, "error": f"timeout ({COLLECTOR_TIMEOUT}s)"})
            except Exception as exc:
                log.error("  Collector %s failed: %s", src, exc)
                results["errors"].append({"stage": "collect", "source": src, "error": str(exc)})

        results["events"] = all_events

        if not all_events:
            log.info("No new events found.")
            return results

        # 2. ANALYZE
        all_analyses: list[Analysis] = []
        for analyzer in self._analyzers:
            aid = analyzer.analyzer_id
            acfg = self.config.analyzers.get(aid, {})
            if not acfg.get("enabled", True):
                continue

            log.info("Running analyzer %s on %d events", aid, len(all_events))
            try:
                analyses = analyzer.analyze(all_events)
                all_analyses.extend(analyses)
            except Exception as exc:
                log.error("  Analyzer %s failed: %s", aid, exc)
                results["errors"].append({"stage": "analyze", "source": aid, "error": str(exc)})

        results["analyses"] = all_analyses

        # 3. VERIFY
        all_verifications: list[VerificationResult] = []
        for verifier in self._verifiers:
            log.info("Running verifier %s", verifier.verifier_id)
            try:
                vrs = verifier.verify(all_events, all_analyses)
                all_verifications.extend(vrs)
            except Exception as exc:
                log.error("  Verifier %s failed: %s", verifier.verifier_id, exc)
                results["errors"].append({"stage": "verify", "source": verifier.verifier_id, "error": str(exc)})

        results["verifications"] = all_verifications

        # Filter out duplicates
        dup_ids = {v.event_id for v in all_verifications if v.is_duplicate}
        unique_events = [e for e in all_events if e.id not in dup_ids]

        # 3.5. INTELLIGENCE (person dossier, decision analysis, document tracking)
        for intel in self._intelligence:
            log.info("Running intelligence %s", type(intel).__name__)
            try:
                intel.process(unique_events, all_analyses)
            except Exception as exc:
                log.error("  Intelligence %s failed: %s", type(intel).__name__, exc)

        # 4. TELEGRAM NOTIFICATIONS (handled by run_pipeline.py)

        # 5. INFOPRIVIDS
        from .drafters.infoprivid import suggest_infoprivids
        try:
            infoprivids = suggest_infoprivids(unique_events, all_analyses, self.state)
            results["infoprivids"] = infoprivids
            log.info("Suggested %d infoprivids", len(infoprivids))
        except Exception as exc:
            log.error("Infoprivid suggestion failed: %s", exc)

        # 6. DRAFT
        all_drafts: list[Draft] = []
        for drafter in self._drafters:
            log.info("Running drafter %s", drafter.drafter_id)
            try:
                drafts = drafter.draft(unique_events, all_analyses, all_verifications)
                all_drafts.extend(drafts)
            except Exception as exc:
                log.error("  Drafter %s failed: %s", drafter.drafter_id, exc)
                results["errors"].append({"stage": "draft", "source": drafter.drafter_id, "error": str(exc)})

        results["drafts"] = all_drafts

        if dry_run:
            log.info("DRY RUN — skipping publish and state save.")
            return results

        # 7. PUBLISH
        for draft in all_drafts:
            for publisher in self._publishers:
                try:
                    ok = publisher.publish(draft, unique_events, all_analyses)
                    if ok:
                        results["published"].append({"draft": draft.title, "publisher": publisher.publisher_id})
                except Exception as exc:
                    log.error("  Publisher %s failed: %s", publisher.publisher_id, exc)
                    results["errors"].append({"stage": "publish", "source": publisher.publisher_id, "error": str(exc)})

        # Mark seen + update cadence + save
        for event in all_events:
            self.state.mark_seen(event.id)
            if event.data.get("person_name"):
                self.state.record_person(event.data["person_name"], event.id)

        self.state.trim_seen()
        self.state.save()

        log.info("Pipeline complete: %d events, %d analyses, %d drafts, %d errors",
                 len(all_events), len(all_analyses), len(all_drafts), len(results["errors"]))
        return results
