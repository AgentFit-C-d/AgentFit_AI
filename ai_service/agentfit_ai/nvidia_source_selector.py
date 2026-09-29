"""Opt-in full source-selector pipeline using a verified NVIDIA NIM model."""

from .deepseek_evaluation import MODEL, NvidiaAnalyzer, post_nvidia
from .source_selector_analysis import SourceSelectorSolarAnalyzer


class NvidiaSourceSelectorAnalyzer(SourceSelectorSolarAnalyzer):
    def __init__(self, api_key, *, model=MODEL, transport=post_nvidia, **kwargs):
        # NvidiaAnalyzer temporarily swaps its parser transport per call.
        if kwargs.get("parallel_first_pass", False):
            raise ValueError("NVIDIA source selector requires sequential calls")
        nvidia = NvidiaAnalyzer(api_key, transport=transport, model=model)
        super().__init__(api_key, transport=transport, model="solar-pro4", **kwargs)
        self._nvidia = nvidia
        self._model = model

    def _send_payload(self, payload, names, *, _trace=None, timeout=40):
        return self._nvidia._send_payload(payload, names, _trace=_trace, timeout=timeout)
