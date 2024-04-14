import signal
import time
from multiprocessing import Process


def run():
    while True:
        time.sleep(1000000000)


signal.signal(signal.SIGINT, signal.SIG_IGN)
for _ in range(20):
    Process(target=run, args=()).start()
