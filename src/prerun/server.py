import code
import json
import multiprocessing
import os
import runpy
import secrets
import signal
import socket
import struct
import subprocess
import sys
from multiprocessing import Pipe, Process

import psutil

from .recv_bytes import recv_bytes
from .sigint import sigint_defer, sigint_once


def run_child(stdio, preloader, conn, files_to_close):
    for f in files_to_close:
        f.close()
    del files_to_close

    multiprocessing.set_start_method(None, force=True)
    os.dup2(sys.stdin.fileno(), 0, inheritable=True)
    signal.signal(signal.SIGINT, signal.default_int_handler)

    sys.argv = [preloader]
    runpy.run_path(preloader)

    data = conn.recv()
    conn.close()

    os.dup2(stdio[0], 0, inheritable=True)
    os.close(stdio[0])
    sys.stdin.close()
    sys.stdin = open(0, closefd=False)

    os.environ.clear()
    for k, v in data["environ"].items():
        os.environ[k] = v
    os.chdir(data["cwd"])

    if not data["args"]:
        import readline
        import rlcompleter

        code_locals = {}
        readline.set_completer(rlcompleter.Completer(code_locals).complete)
        readline.parse_and_bind("tab: complete")
        code.interact(local=code_locals, exitmsg="")
    else:
        sys.argv = list(data["args"])
        runpy.run_path(data["args"][0], run_name="__main__")


def run(stdio, preloader, conn, socks_to_close):
    sigint_defer()

    for s in socks_to_close:
        s.close()
    del socks_to_close

    c1, c2 = Pipe()
    p = Process(target=run_child, args=(stdio, preloader, c2, [conn, c1]))
    p.start()
    c2.close()

    proc = psutil.Process(p.pid)
    if p.exitcode is not None:
        return

    try:
        length = int.from_bytes(recv_bytes(conn, 8))
        data = json.loads(recv_bytes(conn, length).decode("utf-8"))
        pgid = int(data["pgid"])

        os.setpgid(0, pgid)
        os.setpgid(p.pid, pgid)

        conn.sendall(b"\x01")
        assert conn.recv(1) == b"\x01"
    except:
        if p.exitcode is None:
            for child in proc.children(recursive=True):
                child.kill()
            proc.kill()
        raise

    try:
        if data["args"]:
            sigint_once()
        try:
            c1.send({"args": data["args"], "cwd": data["cwd"], "environ": data["environ"]})
        except:
            pass
        c1.close()
        p.join()
        sigint_defer()
    except KeyboardInterrupt:
        if p.exitcode is None:
            try:
                sigint_once()
                p.join()
                sigint_defer()
            except KeyboardInterrupt:
                pass

    if p.exitcode is None:
        for child in proc.children(recursive=True):
            child.kill()
        proc.kill()

    data = json.dumps({"exit_code": p.exitcode if p.exitcode is not None else -signal.SIGKILL}).encode("utf-8")
    conn.sendall(struct.pack(">Q", len(data)) + data)
    conn.close()


def launch_process(stdio, preloader, socks_to_close):
    c1, c2 = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    p = Process(target=run, args=(stdio, preloader, c2, socks_to_close + [c1]))
    p.start()
    c2.close()
    return p, c1


def handler(stdio, preloader, num_proc, sock):
    sigint_defer()

    processes = []
    for _ in range(num_proc):
        processes.append(launch_process(stdio, preloader, [sock] + [x[1] for x in processes]))

    while True:
        c = None
        conn = None
        proc = None
        try:
            c = sock.accept()[0]
            proc, conn = processes[0]
            socket.send_fds(c, [b"\x01"], [conn.fileno()])
            conn.close()
            conn = None
            del proc
            proc = None
            c.close()
            c = None
        except:
            pass
        if conn is not None:
            try:
                conn.close()
            except:
                pass
        if proc is not None:
            del proc
        if c is not None:
            try:
                c.close()
            except:
                pass

        processes = processes[1:]
        processes.append(launch_process(stdio, preloader, [sock] + [x[1] for x in processes]))


def server(args):
    multiprocessing.set_start_method("fork")

    sigint_defer()
    stdio = [os.dup(0)]
    os.set_inheritable(stdio[0], True)

    if len(args) < 1:
        sys.stderr.write("Expected server argument.\n\nSee --help for more information.\n\n")
        return 1
    preloader = args[0]
    num_proc = 4
    if len(args) > 1:
        try:
            num_proc = int(args[1])
        except ValueError:
            sys.stderr.write("Number of processes must be an integer.\n\nSee --help for more information.\n\n")
            return 1

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock_path = secrets.token_hex(16)
    sock_path = f"/tmp/prerun_{sock_path}"
    sock.bind(sock_path)
    sock.listen()

    try:
        p = Process(target=handler, args=(stdio, preloader, num_proc, sock))
        p.start()
        sock.close()

        os.environ["PRERUN_SERVER"] = sock_path
        shell = os.environ.get("SHELL", "/bin/sh")
        proc = subprocess.Popen([shell])
        result = proc.wait()

        parent = psutil.Process()
        for child in parent.children(recursive=True):
            child.kill()
        return result
    finally:
        os.remove(sock_path)
