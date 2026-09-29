"""Opt-in recoverable draft from the existing Solar analysis pipeline."""

from contextvars import ContextVar
from concurrent.futures import ThreadPoolExecutor

from .diagnostics import safe_code
from .profile import FIELDS, validate_profile
from .repair_context_options import build_repair_context_options
from .recoverable_draft import project_draft
from .solar import AnalysisError, SolarAnalyzer


class RecoverableSolarAnalyzer(SolarAnalyzer):
    def __init__(self, *args, **kwargs):
        repair_context_options = kwargs.pop("repair_context_options", False)
        parallel_first_pass = kwargs.pop("parallel_first_pass", False)
        if type(repair_context_options) is not bool:
            raise ValueError("repair_context_options must be boolean")
        if type(parallel_first_pass) is not bool:
            raise ValueError("parallel_first_pass must be boolean")
        if kwargs.get("semantic_review") is False:
            raise ValueError("recoverable Solar analysis requires semantic review")
        super().__init__(*args, **kwargs)
        self._repair_context_options = repair_context_options
        self._parallel_first_pass = parallel_first_pass
        self._draft_context = ContextVar("recoverable_solar_snapshot", default=None)

    def _first_pass(self, request, reserve_call):
        if not self._parallel_first_pass:
            return super()._first_pass(request, reserve_call)
        core = tuple(field for field in FIELDS if field != "features")
        features = ("features",)
        core_call = reserve_call(core, stage="core")
        features_call = reserve_call(features, stage="features")
        with ThreadPoolExecutor(max_workers=2) as pool:
            core_result = pool.submit(
                request, core,
                "Extract confirmed technology and integrations, including external backup storage. Exclude evaluation candidates and examples.",
                _reserved_call=core_call)
            features_result = pool.submit(
                request, features,
                "Extract only confirmed product and operational features as exact source spans.",
                _reserved_call=features_call)
            candidate = core_result.result()
            candidate.update(features_result.result())
        return candidate

    def _repair_correction(self, document, errors, previous):
        correction = super()._repair_correction(document, errors, previous)
        if self._repair_context_options and self._evidence_contract:
            options = build_repair_context_options(document, errors, previous)
            if options:
                correction["evidenceOptions"] = options
        return correction

    def _request_fields(self, document, names, purpose, correction=None, *, _trace=None, timeout=40):
        if correction is not None and "evidenceOptions" in correction:
            purpose += (" For evidenceOptions, choose the supported source occurrence "
                        "and copy its quote and context exactly into the corresponding "
                        "repaired item. Return null if no option supports the fact.")
        return super()._request_fields(document, names, purpose, correction,
                                       _trace=_trace, timeout=timeout)

    def _observe_profile(self, stage, profile):
        snapshot = self._draft_context.get()
        if snapshot is not None:
            snapshot["profile"] = profile
            snapshot["invalid_fields"] = set()
            snapshot["review_complete"] = False

    def _observe_partial_candidate(self, document, document_id, candidate):
        snapshot = self._draft_context.get()
        if snapshot is None:
            return
        data, evidence, invalid = {}, {}, set()
        for field in FIELDS:
            isolated = dict.fromkeys(FIELDS)
            isolated[field] = candidate[field]
            try:
                checked = self._project(document, document_id, isolated)
            except AnalysisError:
                data[field], evidence[field] = None, []
                invalid.add(field)
            else:
                data[field] = checked["data"][field]
                evidence[field] = [{"start": span["start"], "end": span["end"]}
                                   for span in checked["evidence"][field]]
        profile = validate_profile(document, document_id,
                                   {"data": data, "evidence": evidence})
        snapshot["profile"] = profile
        snapshot["invalid_fields"] = invalid
        snapshot["review_complete"] = False

    def _observe_review_issues(self, stage, issues):
        snapshot = self._draft_context.get()
        if snapshot is not None:
            snapshot["review_complete"] = True
            snapshot["issues"].update(issue["field"] for issue in issues)

    def analyze_recoverable(self, document: str, document_id: str) -> dict:
        snapshot = {"profile": None, "issues": set(), "invalid_fields": set(),
                    "review_complete": False}
        token = self._draft_context.set(snapshot)
        try:
            try:
                result = super().analyze(document, document_id)
            except AnalysisError as error:
                profile = snapshot["profile"]
                if profile is None or not any(profile["data"][field] is not None
                                              for field in FIELDS):
                    return {"outcome": "failed", "error": safe_code(error.code)}
                unresolved = {field: "ANALYSIS_UNRESOLVED"
                              for field in snapshot["invalid_fields"]}
                unresolved.update({field: "REVIEW_ISSUE" for field in snapshot["issues"]})
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
