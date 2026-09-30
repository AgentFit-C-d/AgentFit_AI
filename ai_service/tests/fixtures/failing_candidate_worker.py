"""Synthetic pipeline failure through the real worker; all network is forbidden."""
from pathlib import Path
import socket
import sys
from unittest.mock import patch


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from agentfit_ai.analysis_worker import main as worker_main
    from agentfit_ai.candidate_first_profile import CandidatePipelineError

    failure = CandidatePipelineError(sys.argv[1], detail='synthetic-private-detail')
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')), patch.object(
            socket.socket, 'connect_ex', side_effect=AssertionError('network forbidden')), patch(
            'agentfit_ai.candidate_service_worker.find_spec', return_value=object()), patch(
            'agentfit_ai.candidate_service_worker.analyze_integrated_candidates', side_effect=failure):
        return worker_main()


if __name__ == '__main__':
    raise SystemExit(main())
