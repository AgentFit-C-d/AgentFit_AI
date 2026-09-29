"""Opt-in recoverable draft from the existing Solar analysis pipeline."""

from contextvars import ContextVar

from .diagnostics import safe_code
from .profile import FIELDS
from .recoverable_draft import project_draft
from .solar import AnalysisError, SolarAnalyzer


class RecoverableSolarAnalyzer(SolarAnalyzer):
    def __init__(self, *args, **kwargs):
        if kwargs.get("semantic_review") is False:
            raise ValueError("recoverable Solar analysis requires semantic review")
        super().__init__(*args, **kwargs)
        self._draft_context = ContextVar("recoverable_solar_snapshot", default=None)

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
        snapshot = {"profile": None, "issues": set(), "review_complete": False}
        token = self._draft_context.set(snapshot)
        try:
            try:
                result = super().analyze(document, document_id)
            except AnalysisError as error:
                profile = snapshot["profile"]
                if profile is None or not any(profile["data"][field] is not None
                                              for field in FIELDS):
                    return {"outcome": "failed", "error": safe_code(error.code)}
                unresolved = {field: "REVIEW_ISSUE" for field in snapshot["issues"]}
                draft = project_draft(
                    document, document_id, profile, unresolved=unresolved,
                    review_complete=snapshot["review_complete"],
                    error_code=error.code, ask_suggested_when_unreviewed=True,
                    ask_unknown_when_unreviewed=False)
                if not any(state == "suggested" for state in draft["fieldStates"].values()):
                    return {"outcome": "failed", "error": safe_code(error.code)}
                return draft
            return {"outcome": "complete", "profile": result.profile}
        finally:
            self._draft_context.reset(token)
