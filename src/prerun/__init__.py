import os
import sys

from .client import client
from .server import server


def main():
    if len(sys.argv) < 2:
        raise RuntimeError("Expected arguments")

    if sys.argv[1] != "-s":
        server_path = os.environ.get("PRERUN_SERVER")
        if server_path is None:
            raise RuntimeError("No server detected; use -s to start a server")
        return client(sys.argv[1:], server_path)
    else:
        return server(sys.argv[2:])
