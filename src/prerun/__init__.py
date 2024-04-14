import os
import readline
import runpy
import shlex
import signal
import sys
from multiprocessing import Pipe, Process

import psutil


def run(stdio, preloader, conn):
    os.setpgid(0, 0)
    os.dup2(sys.stdin.fileno(), 0, inheritable=True)

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
                    s = input("Next task > ")
                    runner = shlex.split(s)
                except ValueError as e:
                    sys.stderr.write("Error: " + str(e) + "\n")
                    continue
                except EOFError:
                    return
                except KeyboardInterrupt:
                    print("^C")
                    pass

            proc, conn = processes[0]
            processes.append(launch_process(stdio, preloader))

            try:
                conn.send(runner)
                proc.join()
            except KeyboardInterrupt:
                if proc.exitcode is None:
                    parent = psutil.Process(proc.pid)
                    for child in parent.children(recursive=True):
                        child.send_signal(signal.SIGINT)
                    parent.send_signal(signal.SIGINT)

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
    stdio = [os.dup(0)]
    os.set_inheritable(stdio[0], True)

    p = Process(target=real_main, args=(stdio,))
    p.start()
    while True:
        try:
            p.join()
            break
        except KeyboardInterrupt:
            pass
    p.close()
