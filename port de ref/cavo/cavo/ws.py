"""CaVo — WebSocket mínimo (RFC6455) só com stdlib: handshake + frames de texto.

Propositalmente pequeno: sem fragmentação, sem compressão. Mensagens do jogo
têm < 4KB. Cliente mascara (obrigatório), servidor não.
"""
import base64
import hashlib
import os
import socket
import struct

GUID = "258EAFA5-E914-47DA-C95C-AB0C6A4B11CF"
OP_TEXT = 0x1
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA


class WSError(Exception):
    pass


def _recvn(sock, n):
    buf = b""
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
        except socket.timeout as e:
            raise WSError("timeout") from e
        if not chunk:
            raise WSError("conexão fechada")
        buf += chunk
    return buf


def server_handshake(conn):
    """Lê o HTTP do cliente e responde 101. Retorna o path pedido."""
    req = b""
    while b"\r\n\r\n" not in req:
        chunk = conn.recv(4096)
        if not chunk:
            raise WSError("handshake vazio")
        req += chunk
        if len(req) > 16384:
            raise WSError("handshake grande demais")
    head = req.decode("latin-1")
    lines = head.split("\r\n")
    key = ""
    for ln in lines[1:]:
        if ln.lower().startswith("sec-websocket-key:"):
            key = ln.split(":", 1)[1].strip()
    if not key:
        raise WSError("sem Sec-WebSocket-Key")
    accept = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
    conn.sendall(("HTTP/1.1 101 Switching Protocols\r\n"
                  "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                  f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode())
    return lines[0].split(" ")[1] if lines else "/"


def client_handshake(sock, host, path="/"):
    key = base64.b64encode(os.urandom(16)).decode()
    sock.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}\r\n"
                  "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                  f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
    resp = b""
    while b"\r\n\r\n" not in resp:
        chunk = sock.recv(4096)
        if not chunk:
            raise WSError("servidor não respondeu")
        resp += chunk
    if b" 101 " not in resp.split(b"\r\n", 1)[0]:
        raise WSError(f"handshake recusado: {resp[:60]!r}")


def send_msg(sock, data, mask):
    """Enfileira um frame de texto. mask=True p/ cliente->servidor."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    head = bytes([0x80 | OP_TEXT])
    n = len(data)
    if n < 126:
        head += bytes([0x80 | n if mask else n])
    elif n < 65536:
        head += bytes([0x80 | 126 if mask else 126]) + struct.pack(">H", n)
    else:
        head += bytes([0x80 | 127 if mask else 127]) + struct.pack(">Q", n)
    if mask:
        key = os.urandom(4)
        head += key
        data = bytes(b ^ key[i % 4] for i, b in enumerate(data))
    sock.sendall(head + data)


def send_close(sock, mask=False):
    try:
        sock.sendall(bytes([0x88, 0x80 if mask else 0x00]))
    except OSError:
        pass


def recv_msg(sock):
    """Bloqueia até uma mensagem de texto. Ping responde sozinho. None = fechou."""
    while True:
        hdr = _recvn(sock, 2)
        fin = hdr[0] & 0x80
        op = hdr[0] & 0x0F
        masked = hdr[1] & 0x80
        n = hdr[1] & 0x7F
        if n == 126:
            n = struct.unpack(">H", _recvn(sock, 2))[0]
        elif n == 127:
            n = struct.unpack(">Q", _recvn(sock, 8))[0]
        key = _recvn(sock, 4) if masked else None
        payload = _recvn(sock, n) if n else b""
        if masked:
            payload = bytes(b ^ key[i % 4] for i, b in enumerate(payload))
        if op == OP_CLOSE:
            return None
        if op == OP_PING:
            try:
                sock.sendall(bytes([0x8A, 0x00]))
            except OSError:
                pass
            continue
        if op == OP_PONG:
            continue
        if op == OP_TEXT:
            if not fin:
                raise WSError("fragmentação não suportada")
            return payload.decode("utf-8")
        # ignora binário/continuação
