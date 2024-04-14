import multiprocessing
import os
import readline
import runpy
import shlex
import signal
import sys
from multiprocessing import Pipe, Process

import psutil


def sigint_once_handler(signum, frame):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    return signal.default_int_handler(signum, frame)


def run(stdio, preloader, conn):
    multiprocessing.set_start_method(None, force=True)
    os.setpgid(0, 0)
    os.dup2(sys.stdin.fileno(), 0, inheritable=True)
    signal.signal(signal.SIGINT, signal.default_int_handler)

    sys.argv = [preloader]
    runpy.run_path(preloader)

    runner = conn.recv()

    os.dup2(stdio[0], 0, inheritable=True)
    os.close(stdio[0])
    sys.stdin.close()
    sys.stdin = open(0, closefd=False)

    sys.argv = list(runner)
    runpy.run_path(runner[0], run_name="__main__")


def launch_process(stdio, preloader):
    c1, c2 = Pipe(duplex=True)
    p = Process(target=run, args=(stdio, preloader, c2))
    p.start()
    return p, c1


def real_main(stdio):
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    os.dup2(stdio[0], 0, inheritable=True)
    sys.stdin.close()
    sys.stdin = open(0, closefd=False)

    preloader, num_proc, runner = sys.argv[1], int(sys.argv[2]), sys.argv[3:]

    processes = []
    for _ in range(num_proc):
        processes.append(launch_process(stdio, preloader))

    if runner:
        readline.add_history(shlex.join(runner))

    try:
        while True:
            while not runner:
                try:
                    signal.signal(signal.SIGINT, sigint_once_handler)
                    try:
                        s = input("Next task > ")
                    except EOFError:
                        signal.signal(signal.SIGINT, signal.SIG_IGN)
                        return
                    signal.signal(signal.SIGINT, signal.SIG_IGN)
                    try:
                        runner = shlex.split(s)
                    except ValueError as e:
                        sys.stderr.write("Error: " + str(e) + "\n")
                        continue
                except KeyboardInterrupt:
                    print("^C")

            proc, conn = processes[0]
            processes.append(launch_process(stdio, preloader))

            if proc.exitcode is None:
                os.setpgid(proc.pid, os.getpgid(0))

            try:
                signal.signal(signal.SIGINT, sigint_once_handler)
                conn.send(runner)
                proc.join()
                signal.signal(signal.SIGINT, signal.SIG_IGN)
            except KeyboardInterrupt:
                if proc.exitcode is None:
                    proc.join(0.5)

            if proc.exitcode is None:
                parent = psutil.Process(proc.pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()

            del proc
            conn.close()

            processes = processes[1:]
            runner = []
    finally:
        for proc, _ in processes:
            if proc.exitcode is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.kill()
        os._exit(0)


def main():
    multiprocessing.set_start_method("fork")

    signal.signal(signal.SIGINT, signal.SIG_IGN)
    stdio = [os.dup(0)]
    os.set_inheritable(stdio[0], True)

    p = Process(target=real_main, args=(stdio,))
    p.start()
    p.join()
    p.close()
