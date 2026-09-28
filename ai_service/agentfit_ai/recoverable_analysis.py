"""Opt-in recoverable outcome for the anchored analyzer."""

from contextvars import ContextVar

from .anchored_analysis import AnchoredAnalyzer
from .diagnostics import safe_code
from .profile import FIELDS
from .recoverable_draft import project_draft
from .recoverable_judgment import salvage_judgment
from .solar import AnalysisError


class RecoverableAnchoredAnalyzer(AnchoredAnalyzer):
    """Keep only verified snapshots for the duration of one optional call."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._draft_context = ContextVar("recoverable_anchored_snapshot", default=None)

    def _observe_judgment_failure(self, reply, pool, document, document_id, error):
        snapshot = self._draft_context.get()
        if snapshot is not None:
            snapshot["judgment"] = (reply, pool)

    def _observe_profile(self, stage, profile):
        snapshot = self._draft_context.get()
        if snapshot is not None:
            snapshot["profile"] = profile
            snapshot["review_complete"] = False

    def _observe_review_issues(self, stage, issues):
        snapshot = self._draft_context.get()
        if snapshot is not None:
            snapshot["review_complete"] = True
            snapshot["issues"].update(issue["field"] for issue in issues)

    def analyze_recoverable(self, document: str, document_id: str) -> dict:
        snapshot = {"profile": None, "judgment": None, "issues": set(),
                    "review_complete": False}
        token = self._draft_context.set(snapshot)
        try:
            try:
                result = super().analyze(document, document_id)
            except AnalysisError as error:
                profile = snapshot["profile"]
                unresolved = {field: "REVIEW_ISSUE" for field in FIELDS
                              if field in snapshot["issues"]}
                if profile is None and snapshot["judgment"] is not None:
                    reply, pool = snapshot["judgment"]
                    profile, judgment_issues = salvage_judgment(
                        document, document_id, pool, reply)
                    unresolved.update(judgment_issues)
                if profile is None:
                    return {"outcome": "failed", "error": safe_code(error.code)}
                return project_draft(document, document_id, profile,
                                     unresolved=unresolved,
                                     review_complete=snapshot["review_complete"],
                                     error_code=error.code)
            return {"outcome": "complete", "profile": result.profile}
        finally:
            self._draft_context.reset(token)
