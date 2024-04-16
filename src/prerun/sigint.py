import signal

SIGINT_PENDING = False


def sigint_defer_handler(signum, frame):
    global SIGINT_PENDING
    SIGINT_PENDING = True


def sigint_once_handler(signum, frame):
    global SIGINT_PENDING
    signal.signal(signal.SIGINT, sigint_defer_handler)
    SIGINT_PENDING = False
    raise KeyboardInterrupt


def sigint_defer():
    signal.signal(signal.SIGINT, sigint_defer_handler)


def sigint_once():
    global SIGINT_PENDING
    signal.signal(signal.SIGINT, sigint_once_handler)
    if SIGINT_PENDING:
        signal.signal(signal.SIGINT, sigint_defer_handler)
        SIGINT_PENDING = False
        raise KeyboardInterrupt
