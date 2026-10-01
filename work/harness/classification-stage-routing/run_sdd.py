"""Run existing SDD helpers with process-local Git trust on this Windows host."""
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[3]
skill = Path('C:/Users/fhtkr/.codex/plugins/cache/openai-curated-remote/superpowers/6.4.2/skills')
action = sys.argv[1]
owners = {'sdd-workspace': 'subagent-driven-development',
          'review-package': 'subagent-driven-development',
          'task-start': 'executing-plans', 'task-done': 'executing-plans'}
env = dict(os.environ, GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='safe.directory',
           GIT_CONFIG_VALUE_0=root.as_posix(), PYTHONPATH=str(root / 'ai_service'))
result = subprocess.run(['C:/Program Files/Git/bin/bash.exe',
    str(skill / owners[action] / 'scripts' / action), *sys.argv[2:]],
    cwd=root, env=env, timeout=180)
raise SystemExit(result.returncode)
