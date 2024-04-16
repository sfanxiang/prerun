import json
import os
import socket
import struct

from .recv_bytes import recv_bytes
from .sigint import sigint_defer


def client(args, server):
    sigint_defer()

    cwd = os.getcwd()
    environ = os.environ.copy()
    pgid = os.getpgid(0)

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(server)
    buf, fds, _, _ = socket.recv_fds(sock, 1, 1)
    if not buf:
        raise EOFError
    sock.close()

    sock = socket.socket(fileno=fds[0])
    data = json.dumps({"args": args, "cwd": cwd, "environ": environ, "pgid": pgid}).encode("utf-8")
    sock.sendall(struct.pack(">Q", len(data)) + data)
    assert sock.recv(1) == b"\x01"
    sock.sendall(b"\x01")

    length = int.from_bytes(recv_bytes(sock, 8), byteorder="big")
    data = json.loads(recv_bytes(sock, length).decode("utf-8"))
    sock.close()

    return int(data["exit_code"])
