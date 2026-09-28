"""Call-local observations for the opt-in false-complete evaluator."""

from contextvars import ContextVar
from copy import deepcopy

from .recoverable_analysis import RecoverableAnchoredAnalyzer


class ObservedRecoverableAnalyzer(RecoverableAnchoredAnalyzer):
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
        observation = {"candidates": [], "profiles": [], "reviews": []}
        token = self._observation_context.set(observation)
        try:
            result = self.analyze_recoverable(document, document_id)
            return result, observation
        finally:
            self._observation_context.reset(token)
