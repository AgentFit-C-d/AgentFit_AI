"""Test-only worker entry point: real pipeline, loopback endpoints, no nested processes."""
from pathlib import Path
import socket
import subprocess
import sys
from urllib.parse import urlsplit


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    endpoint = sys.argv[1]
    parsed = urlsplit(endpoint)
    if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or not parsed.port:
        raise ValueError('fixture requires loopback')
    original_connect = socket.socket.connect
    def local_connect(sock, address):
        if address != ('127.0.0.1', parsed.port):
            raise AssertionError('external network forbidden')
        return original_connect(sock, address)
    socket.socket.connect = local_connect
    class NoChildren(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            raise AssertionError('nested provider process forbidden')
    subprocess.Popen = NoChildren
    from agentfit_ai import solar, nvidia_streaming
    solar.ENDPOINT = endpoint + '/solar'
    nvidia_streaming.ENDPOINT = endpoint + '/nvidia'
    if sys.argv[2:] == ['evaluation']:
        from agentfit_ai.independent_evaluation_worker import main as worker_main
    else:
        from agentfit_ai.analysis_worker import main as worker_main
    raise SystemExit(worker_main())


if __name__ == '__main__':
    main()
