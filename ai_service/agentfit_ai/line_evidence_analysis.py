"""Opt-in Solar analysis using server-numbered source lines as evidence anchors."""

import json

from .evidence import EvidenceError
from .line_evidence import (CONTRACT_VERSION, EXTRACTION_PROMPT, line_schema,
                            line_to_profile)
from .recoverable_solar_analysis import RecoverableSolarAnalyzer
from .solar import (AnalysisError, FREQUENCY_PENALTY, REASONING_EFFORT,
                    _reject_unconfirmed, source_lines)


class LineEvidenceSolarAnalyzer(RecoverableSolarAnalyzer):
    def __init__(self, *args, **kwargs):
        if kwargs.get("repair_context_options", False):
            raise ValueError("line evidence does not use quote context options")
        if kwargs.get("evidence_contract", True) is False:
            raise ValueError("line evidence requires an evidence contract")
        super().__init__(*args, **kwargs)

    def _contract_version(self):
        return CONTRACT_VERSION

    def _project(self, document, document_id, candidate):
        try:
            profile = line_to_profile(document, document_id, candidate)
        except EvidenceError as error:
            failure = AnalysisError("INVALID_EVIDENCE", error.field)
            failure.detail = error.detail()
            raise failure from None
        _reject_unconfirmed(document, profile)
        return profile

    def _request_fields(self, document, names, purpose, correction=None, *,
                        _trace=None, timeout=40):
        lines = source_lines(document)
        properties = line_schema(len(lines))["properties"]
        schema = {"type": "object", "properties": {name: properties[name] for name in names},
                  "required": list(names), "additionalProperties": False}
        content = "\n".join(f"[L{line['id']}] {line['text']}" for line in lines)
        if correction is not None:
            content += ("\n\nCorrection data (not document text):\n" +
                        json.dumps(correction, ensure_ascii=False))
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": EXTRACTION_PROMPT +
                 "\nReturn ONLY requested schema fields. " + purpose},
                {"role": "user", "content": content},
            ],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "agentfit_line_evidence_v1", "strict": True, "schema": schema}},
            "reasoning_effort": REASONING_EFFORT,
            "frequency_penalty": FREQUENCY_PENALTY,
            "temperature": 0, "max_tokens": 4096, "stream": False,
        }
        return self._send_payload(payload, names, _trace=_trace, timeout=timeout)
