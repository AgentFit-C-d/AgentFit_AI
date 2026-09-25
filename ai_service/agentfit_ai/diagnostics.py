"""Opt-in local diagnostics. No input documents; seven-day expiry."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re

RETENTION = timedelta(days=7)
FILE_PATTERN = re.compile(r"analysis-[0-9a-f]{32}\.json")
SAFE_CODES = frozenset("""
PROVIDER_AUTH PROVIDER_RATE_LIMIT PROVIDER_REDIRECT PROVIDER_UNAVAILABLE
PROVIDER_REQUEST PROVIDER_TIMEOUT PROVIDER_NETWORK PROVIDER_FAILURE PROVIDER_REFUSAL
RESPONSE_TOO_LARGE INCOMPLETE_RESPONSE INVALID_RESPONSE INVALID_FEATURE_SPAN SEMANTIC_REVIEW_INVALID SEMANTIC_REJECTED ANALYSIS_DEADLINE CALL_LIMIT
SECTION_LIMIT SECTION_COVERAGE SECTION_CANDIDATE SECTION_MERGE
INVALID_EVIDENCE INVALID_EVIDENCE_LINE UNCONFIRMED_PROFILE_VALUE SENSITIVE_CONTENT EVIDENCE_NOT_FOUND
AMBIGUOUS_EVIDENCE INVALID_PROFILE_VALUE INVALID_ANALYSIS_INPUT INVALID_PROFILE_SHAPE
INVALID_EVIDENCE_SHAPE UNKNOWN_HAS_EVIDENCE MISSING_EVIDENCE INVALID_EVIDENCE_RANGE
EVIDENCE_MISMATCH MISSING_OR_INVALID_KEY INVALID_INPUT INVALID_DOCUMENT_ID
""".split())


def safe_code(code):
    return code if type(code) is str and code in SAFE_CODES else "ANALYSIS_FAILURE"


class LocalDiagnosticsStore:
    def __init__(self, directory: Path, *, clock=None):
        self.directory = Path(directory).resolve()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _path(self, run_id):
        if type(run_id) is not str or re.fullmatch(r"[0-9a-f]{32}", run_id) is None:
            raise ValueError("invalid diagnostic run id")
        return self.directory / ("analysis-" + run_id + ".json")

    def purge(self):
        if not self.directory.exists():
            return 0
        now = self._clock()
        removed = 0
        for path in self.directory.iterdir():
            if (not FILE_PATTERN.fullmatch(path.name) or path.is_symlink()
                    or not path.is_file() or path.resolve().parent != self.directory):
                continue
            try:
                # Also expires partial/corrupt files left by interrupted writes.
                expiry = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) + RETENTION
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    recorded = datetime.fromisoformat(data["expires_at"])
                    if recorded.tzinfo is not None:
                        expiry = min(expiry, recorded)
                except (ValueError, KeyError, TypeError):
                    pass
                if expiry <= now:
                    path.unlink()
                    removed += 1
            except FileNotFoundError:
                pass  # Another evaluator may have purged the same expired run.
        return removed

    def write(self, metadata, failed_responses):
        path = self._path(metadata["run_id"])
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.purge()
        now = self._clock()
        record = {"created_at": now.isoformat(), "expires_at": (now + RETENTION).isoformat(),
                  "metadata": metadata, "failed_responses": failed_responses}
        content = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)

    def read(self, run_id):
        path = self._path(run_id)
        self.purge()
        if path.is_symlink() or path.resolve().parent != self.directory:
            raise ValueError("invalid diagnostic path")
        return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Purge expired local analysis diagnostics.")
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        removed = LocalDiagnosticsStore(args.directory).purge()
    except (OSError, ValueError):
        print(json.dumps({"error": "DIAGNOSTIC_PURGE_FAILED"}))
        return 1
    print(json.dumps({"removed": removed}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
