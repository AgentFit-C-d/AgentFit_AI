import json
import unittest

from agentfit_ai.paired_review_model_evaluation import (
    CaptureTransport, ReplayTransport, ReplayMismatch, adjusted_deadline,
    aggregate,
)


class PairedReviewModelEvaluationTests(unittest.TestCase):
    def test_same_upstream_request_replays_once_and_later_call_goes_live(self):
        calls = []

        def provider(payload, key, timeout):
            calls.append(payload)
            return b'{"private":"response"}' if len(calls) == 1 else b"later"

        secret = b"local-hmac-key"
        capture = CaptureTransport(secret, provider)
        payload = {"messages": [{"content": "private document"}]}
        self.assertEqual(capture(payload, "key", 40), b'{"private":"response"}')
        replay = ReplayTransport(capture.records, secret, provider)
        self.assertEqual(replay(payload, "key", 40), b'{"private":"response"}')
        self.assertEqual(replay(payload, "key", 40), b"later")
        self.assertEqual(replay.replayed_calls, 1)
        self.assertEqual(len(calls), 2)
        self.assertNotIn("private document", json.dumps(capture.public_fingerprints()))
        self.assertNotIn("private", json.dumps(capture.public_fingerprints()))

    def test_changed_upstream_request_fails_closed(self):
        capture = CaptureTransport(b"secret", lambda *_: b"raw")
        capture({"document": "A"}, "key", 40)
        replay = ReplayTransport(capture.records, b"secret", lambda *_: self.fail("live call"))
        with self.assertRaises(ReplayMismatch):
            replay({"document": "B"}, "key", 40)

    def test_upstream_time_is_subtracted_from_deadline(self):
        self.assertEqual(adjusted_deadline(160, 13000), 147)

    def test_shared_failures_are_excluded_from_model_comparison(self):
        rows = [{"kind": "full", "gold_total": 10, "common_error": "PROVIDER_TIMEOUT",
                 "baseline": {"error": "PROVIDER_TIMEOUT", "provider_calls": 1},
                 "compact": {"error": "PROVIDER_TIMEOUT", "provider_calls": 1}}]
        summary = aggregate(rows)
        self.assertEqual(summary["comparable_cases"], 0)
        self.assertEqual(summary["shared_failures"], {"PROVIDER_TIMEOUT": 1})


if __name__ == "__main__":
    unittest.main()
