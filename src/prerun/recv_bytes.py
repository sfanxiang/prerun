def recv_bytes(sock, n):
    buffer = b""
    while len(buffer) < n:
        new_buffer = sock.recv(n - len(buffer))
        if not new_buffer:
            raise EOFError
        buffer += new_buffer
    return buffer
