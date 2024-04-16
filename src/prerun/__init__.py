import os
import sys

from .client import client
from .server import server

SAVED = {}


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--help":
        print("Start server:\n\t-s <PRELOADER> [NUM_PROCESSES]\n\nRun Python program:\n\t[FILE [ARG...]]\n")
        return 0

    if len(sys.argv) < 2 or sys.argv[1] != "-s":
        server_path = os.environ.get("PRERUN_SERVER")
        if server_path is None:
            sys.stderr.write(
                "No server detected; use argument `-s <PRELOADER>` to start a server.\n\nSee --help for more information.\n\n"
            )
            return 1
        return client(sys.argv[1:], server_path)
    else:
        return server(sys.argv[2:])
