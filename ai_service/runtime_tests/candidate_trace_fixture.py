"""Reuse the existing loopback-only SDK fixture with the opt-in probe worker."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentfit_ai import analysis_worker
import integrated_service_fixture

endpoint, trace_path = sys.argv[1:]


def probe_main():
    from diagnostic_tools.candidate_trace_worker import main
    sys.argv = [sys.argv[0], trace_path]
    main()


analysis_worker.main = probe_main
sys.argv = [sys.argv[0], endpoint, 'nvidia-only']
integrated_service_fixture.main()
