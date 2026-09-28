"""Call-local observations for the opt-in false-complete evaluator."""

from contextvars import ContextVar
from copy import deepcopy

from .recoverable_analysis import RecoverableAnchoredAnalyzer


class ObservedRecoverableAnalyzer(RecoverableAnchoredAnalyzer):
    _SAFE_MERGE_REASONS = frozenset({
        "INVALID_DECISIONS", "SELECTED_COUNT", "CONFLICTING_FACTS",
        "SELECTED_SCOPE", "SELECTED_STATUS", "SELECTED_ROLE",
        "ABSENCE_MULTIPLE", "DUPLICATE_VALUE", "PROFILE_INVALID",
    })

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._observation_context = ContextVar("false_complete_observation", default=None)

    def _observe_candidate_pool(self, pool):
        observation = self._observation_context.get()
        if observation is not None:
            observation["candidates"] = [
                {"id": item["id"], "start": item["span"]["start"],
                 "end": item["span"]["end"]} for item in pool
            ]

    def _observe_judgment_failure(self, reply, pool, document, document_id, error):
        super()._observe_judgment_failure(reply, pool, document, document_id, error)
        observation = self._observation_context.get()
        if observation is not None:
            detail = getattr(error, "merge_detail", None)
            reason = detail.get("reason") if type(detail) is dict else None
            observation["judgment_failure_reason"] = (
                reason if reason in self._SAFE_MERGE_REASONS else None)

    def _observe_profile(self, stage, profile):
        super()._observe_profile(stage, profile)
        observation = self._observation_context.get()
        if observation is not None:
            observation["profiles"].append((stage, deepcopy(profile)))

    def _observe_review_issues(self, stage, issues):
        super()._observe_review_issues(stage, issues)
        observation = self._observation_context.get()
        if observation is not None:
            observation["reviews"].append((stage, [
                {"field": item["field"], "kind": item["kind"]} for item in issues
            ]))

    def analyze_observed(self, document: str, document_id: str) -> tuple[dict, dict]:
        observation = {"candidates": [], "profiles": [], "reviews": [],
                       "judgment_failure_reason": None}
        token = self._observation_context.set(observation)
        try:
            result = self.analyze_recoverable(document, document_id)
            return result, observation
        finally:
            self._observation_context.reset(token)
