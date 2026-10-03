"""Test process only: deny external socket/DNS I/O, including Python children."""
import ipaddress
import os
from pathlib import Path
import sys

GUARD=str(Path(__file__).resolve().parent)


def local(host):
    if host is None: return True  # passive local bind lookup
    if isinstance(host,bytes): host=host.decode('ascii')
    if host in ('localhost',''): return True
    try: return ipaddress.ip_address(host).is_loopback
    except ValueError: return False


def audit(event,args):
    if event in ('socket.connect','socket.sendto'):
        address=args[-1]
        if isinstance(address,tuple) and not local(address[0]):
            raise OSError('EXTERNAL_NETWORK_FORBIDDEN')
    elif event in ('socket.getaddrinfo','socket.gethostbyname','socket.gethostbyaddr'):
        if not local(args[0]): raise OSError('EXTERNAL_NETWORK_FORBIDDEN')
    elif event=='subprocess.Popen':
        env=args[3]
        if env is not None:
            path=env.get('PYTHONPATH','')
            if GUARD not in path.split(os.pathsep): env['PYTHONPATH']=GUARD+os.pathsep+path


sys.addaudithook(audit)
