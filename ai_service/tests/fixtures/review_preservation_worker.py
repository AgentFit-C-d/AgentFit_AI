"""Disposable pipe worker replay; no network and no credentials."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from review_preservation_fixture import replay_providers
from agentfit_ai.analysis_worker import main

with replay_providers():
    main()
