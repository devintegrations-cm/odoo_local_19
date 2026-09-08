#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simulador de datáfono Credibanco para probar el POS sin hardware.

Utilidad de desarrollo: no la importa Odoo ni forma parte de la instalación del
modulo.  Se corre en la maquina del datáfono (o en cualquier host que el
metodo de pago tenga configurado como "Host del datáfono") y el POS habla con
el por WebSocket, igual que con el dispositivo real.

    python3 credibanco_fake_terminal.py --port 8080 --outcome approved

Suites de resultados (`--outcome`):
    approved      respuesta 00, cobro aprobado (con propina en el campo 81)
    rejected      respuesta 02, el cliente declina
    no-answer     no contesta: sirve para ver el timeout y la recuperacion
    recover-then  primera venta queda "03" y la recuperacion la aprueba
    bad-lrc       el datdfono responde 06 (error de trama) aunque la trama sea valida

El servidor valida el LRC de cada trama entrante, asi que tambien comprueba que
el POS arma bien los paquetes.
"""
import argparse
import base64
import hashlib
import json
import socket
import struct
import sys
import threading

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

OP_TEXT = 0x1
OP_CLOSE = 0x8
OP_PING = 0x9


def compute_lrc(text):
    """Same checksum the terminal expects, matching the POS implementation."""
    if not text:
        return ""
    acc = ord(text[0])
    for char in text[1:]:
        acc ^= ord(char)
    return format(acc, "02x")


def split_packet(payload):
    """`name_<campos><lrc>` -> (name, [campos], lrc, trama-sin-nombre)."""
    name, _, rest = payload.partition("_")
    fields_and_lrc = rest
    lrc = fields_and_lrc[-2:]
    trama = fields_and_lrc[:-2]
    return name, trama.split(","), lrc, trama


# Positions each answer really carries, straight out of
# api_credibanco_dkr/resource/functionsFields.ini (OUTPUT_FIELDS_**).  The
# bridge serialises these as a JSON OBJECT keyed by position, which is why the
# simulator must not answer with a bare array: the POS would see a shape that no
# real device produces.
OUTPUT_FIELDS = {
    "00": [0, 1, 40, 41, 80, 43, 44, 45, 46, 47, 48, 49, 50, 51, 54,
           75, 76, 77, 78, 79, 89, 90],                      # Recuperacion
    "01": [0, 1, 40, 41, 42, 80, 43, 44, 45, 46, 47, 48, 49, 50, 51, 53, 54,
           75, 76, 77, 78, 79, 83, 85, 86, 87, 88],           # Compra
    "02": [0, 1, 40, 41, 80, 43, 44, 45, 46, 47, 48, 49, 50, 51, 54,
           75, 76, 77, 78, 79, 89, 90],                       # Anulacion
}


def build_answer(code, total="0", iva="0", tip="0", iac="0", terminal_id="",
                 transaction_number="", cashier="", reference="", auth="A12345",
                 tx="TX999", operation="01"):
    """Answer of `operation`, as a JSON object keyed by protocol position.

    The positions the POS sent (42, 53, 83, 40, 41) are echoed back: a device
    does not invent them, and echoing is what lets the simulator prove that
    cancellation and recovery reuse the right references.  Position 43 is the
    device's own reference.

    Note there is no 81 (tip) nor 82 (IAC) in any answer: they are request-only.
    Position 80 is filled with the tip on purpose -- whether the real device puts
    the tip there or reports the final total in 40 is exactly what is still
    unconfirmed, and this makes the difference visible in development.
    """
    values = {
        "0": code,
        "1": auth,
        "2": tx,
        "40": str(total),
        "41": str(iva),
        "42": str(terminal_id),
        "43": str(reference),
        "53": str(transaction_number),
        "80": str(tip),
        "81": str(tip),
        "82": str(iac),
        "83": str(cashier),
    }
    answer = {}
    for position in OUTPUT_FIELDS.get(operation, OUTPUT_FIELDS["01"]):
        answer[str(position)] = values.get(str(position), "")
    return json.dumps(answer)


# Codes used by this simulator for the cases the protocol has no dedicated one.
CODE_UNKNOWN_TRANSACTION = "91"


def read_frame(conn):
    """One WebSocket frame -> (opcode, str payload) or None when closed."""
    header = _read_exact(conn, 2)
    if header is None:
        return None
    first, second = header[0], header[1]
    opcode = first & 0x0F
    masked = second & 0x80
    length = second & 0x7F
    if length == 126:
        raw = _read_exact(conn, 2)
        length = struct.unpack(">H", raw)[0]
    elif length == 127:
        length = struct.unpack(">Q", _read_exact(conn, 8))[0]
    mask = _read_exact(conn, 4) if masked else None
    data = _read_exact(conn, length) if length else b""
    if data is None:
        return None
    if mask:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return opcode, data.decode("utf-8", "replace")


def write_frame(conn, text):
    payload = text.encode("utf-8")
    header = bytes([0x80 | OP_TEXT])
    length = len(payload)
    if length < 126:
        header += bytes([length])
    elif length < 65536:
        header += bytes([126]) + struct.pack(">H", length)
    else:
        header += bytes([127]) + struct.pack(">Q", length)
    conn.sendall(header + payload)


def _read_exact(conn, count):
    buffer = b""
    while len(buffer) < count:
        chunk = conn.recv(count - len(buffer))
        if not chunk:
            return None
        buffer += chunk
    return buffer


def handshake(conn):
    request = b""
    while b"\r\n\r\n" not in request:
        chunk = conn.recv(4096)
        if not chunk:
            return False
        request += chunk
    headers = {}
    for line in request.decode("latin-1").split("\r\n")[1:]:
        key, _, value = line.partition(":")
        headers[key.strip().lower()] = value.strip()
    key = headers.get("sec-websocket-key")
    if not key:
        conn.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
        return False
    accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Accept: %s\r\n\r\n" % accept
    )
    conn.sendall(response.encode())
    return True


class Terminal:
    """Scripted behaviour of the device, shared by every connection.

    Approved sales are remembered by ``(42, 53)`` so anulación and recuperación
    can only succeed for a transaction that really exists: without that, a
    duplicated or invented transaction number would be silently "approved" and a
    real collision would never show up during development.
    """

    def __init__(self, outcome, terminal_name):
        self.outcome = outcome
        self.terminal_name = terminal_name
        self.sales = {}
        self.recovery_seen = {}
        self.lock = threading.Lock()
        self._reference = 0

    def _next_reference(self):
        self._reference += 1
        return "%06d" % self._reference

    def respond(self, payload):
        name, fields, checksum, trama = split_packet(payload)
        if name != self.terminal_name:
            # The device only answers to its own name; silence is a real mode.
            return None
        if compute_lrc(trama) != checksum:
            return build_answer("06")
        code = fields[0]
        with self.lock:
            if code == "01":  # compra
                return self._sale(fields)
            if code == "02":  # anulacion
                return self._cancel(fields)
            if code == "00":  # recuperacion
                return self._recover(fields)
        return build_answer("06")

    def _sale(self, fields):
        def value(index, default="0"):
            return fields[index] if index < len(fields) and fields[index] != "" else default

        sale = {
            "total": value(1),
            "iva": value(2),
            "terminal_id": value(3, self.terminal_name),
            "transaction_number": value(4),
            "tip": value(5),
            "iac": value(6),
            "cashier": value(7),
            "reference": self._next_reference(),
        }
        key = (sale["terminal_id"], sale["transaction_number"])
        if key in self.sales:
            # A duplicated transaction number is a defect on the caller side.
            return build_answer(CODE_UNKNOWN_TRANSACTION, reference=sale["reference"],
                                operation="01")
        if self.outcome == "rejected":
            return self._answer("02", sale)
        if self.outcome == "no-answer":
            return None
        if self.outcome == "bad-lrc":
            return build_answer("06")
        if self.outcome == "recover-then":
            self.sales[key] = sale
            return self._answer("03", sale)
        self.sales[key] = sale
        return self._answer("00", sale)

    def _cancel(self, fields):
        def value(index, default=""):
            return fields[index] if index < len(fields) else default

        key = (value(1), value(3))
        sale = self.sales.get(key)
        if sale is None:
            return build_answer(
                CODE_UNKNOWN_TRANSACTION,
                terminal_id=key[0],
                transaction_number=key[1],
                operation="02",
            )
        if self.outcome == "no-answer":
            return None
        del self.sales[key]
        return self._answer(
            "00",
            dict(sale, reference=value(2) or sale["reference"]),
            operation="02",
        )

    def _recover(self, fields):
        def value(index, default=""):
            return fields[index] if index < len(fields) else default

        key = (value(1), value(2))
        sale = self.sales.get(key)
        if sale is None:
            return build_answer(
                CODE_UNKNOWN_TRANSACTION,
                terminal_id=key[0],
                transaction_number=key[1],
                operation="00",
            )
        if self.outcome == "no-answer":
            return None
        if self.outcome == "recover-then" and not self.recovery_seen.get(key):
            # First recovery attempt still pending, like a device that is slow.
            self.recovery_seen[key] = True
            return self._answer("03", sale)
        del self.sales[key]
        return self._answer("00", sale)

    def _answer(self, code, sale, operation="01"):
        return build_answer(
            code,
            total=sale["total"],
            iva=sale["iva"],
            tip=sale["tip"],
            iac=sale["iac"],
            terminal_id=sale["terminal_id"],
            transaction_number=sale["transaction_number"],
            cashier=sale["cashier"],
            reference=sale["reference"],
            operation=operation,
        )


def serve(conn, terminal):
    conn.settimeout(3600)
    try:
        if not handshake(conn):
            return
        while True:
            frame = read_frame(conn)
            if frame is None:
                return
            opcode, text = frame
            if opcode == OP_CLOSE:
                return
            if opcode == OP_PING:
                write_frame(conn, "")
                continue
            if opcode != OP_TEXT:
                continue
            answer = terminal.respond(text)
            print("  trama  <- %s" % text)
            if answer is None:
                print("  (sin respuesta, a proposito)")
                continue
            print("  respuesta -> %s" % answer)
            write_frame(conn, answer)
    except (OSError, ValueError) as error:
        print("  conexion terminada: %s" % error, file=sys.stderr)
    finally:
        conn.close()


def selftest():
    """Proves that this tool and the POS agree on the framing and the echo."""
    def packet(trama):
        return "dataf001_" + trama + compute_lrc(trama)

    sale_trama = "01,25000,3991,12905,000042,2000,2500,Juan,,"
    terminal = Terminal("approved", "dataf001")
    answer = json.loads(terminal.respond(packet(sale_trama)))

    # The answer is a JSON object keyed by protocol position, and it only carries
    # the positions of OUTPUT_FIELDS_01 (no 81, no 82): an array-shaped answer
    # would be a shape no real device produces.
    assert answer["0"] == "00", answer
    assert answer["40"] == "25000" and answer["41"] == "3991", answer
    assert answer["42"] == "12905" and answer["53"] == "000042", answer
    assert answer["83"] == "Juan" and answer["43"], answer
    assert "81" not in answer and "82" not in answer, sorted(answer)
    assert answer["80"] == "2000", answer

    name, fields, checksum, trama = split_packet(packet(sale_trama))
    assert name == "dataf001" and compute_lrc(trama) == checksum
    assert fields[1] == "25000", fields

    # The same (42, 53) twice must be refused, not approved twice.
    duplicate = json.loads(terminal.respond(packet(sale_trama)))
    assert duplicate["0"] == CODE_UNKNOWN_TRANSACTION, duplicate

    # Cancelling a transaction number the device never saw is refused (42, 53 is
    # the key the terminal looks the sale up by).
    unknown = json.loads(terminal.respond(packet("02,12905,000099,999999,Juan,,2,")))
    assert unknown["0"] == CODE_UNKNOWN_TRANSACTION, unknown

    # ... while cancelling a real one echoes the references of the sale, and its
    # answer has no 42/53 (OUTPUT_FIELDS_02), which is why the POS cannot match
    # that answer by the request and must rely on the bridge replying in order.
    cancel = json.loads(
        terminal.respond(packet("02,12905,%s,000042,Juan,,2," % answer["43"]))
    )
    assert cancel["0"] == "00" and cancel["43"] == answer["43"], cancel
    assert "42" not in cancel and "53" not in cancel, sorted(cancel)

    # A terminal that does not recognise the message name stays silent, which is
    # what the POS timeout has to cover.
    other_name = "01,10,0,x,1,0,0,Ana,"
    assert terminal.respond("otra_" + other_name + compute_lrc(other_name)) is None

    # recover-then: first "03", then the recovery completes it.
    recovering = Terminal("recover-then", "dataf001")
    first = json.loads(recovering.respond(packet(sale_trama)))
    assert first["0"] == "03", first
    pend = json.loads(recovering.respond(packet("00,12905,000042,")))
    assert pend["0"] == "03", pend
    done = json.loads(recovering.respond(packet("00,12905,000042,")))
    assert done["0"] == "00" and done["40"] == "25000", done

    print("selftest OK: respuestas por posicion, eco de referencias, duplicados y "
          "recuperacion/anulacion")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--name", default="dataf001", help="Nombre de la terminal")
    parser.add_argument(
        "--outcome",
        default="approved",
        choices=("approved", "rejected", "no-answer", "recover-then", "bad-lrc"),
    )
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    terminal = Terminal(args.outcome, args.name)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((args.host, args.port))
    listener.listen(16)
    print(
        "Datfono falso Credibanco en ws://%s:%d/ws  (outcome=%s, nombre=%s)"
        % (args.host if args.host != "0.0.0.0" else "este-equipo", args.port, args.outcome, args.name)
    )
    try:
        while True:
            conn, peer = listener.accept()
            print("conexion de %s" % (peer,))
            threading.Thread(target=serve, args=(conn, terminal), daemon=True).start()
    except KeyboardInterrupt:
        print("\nterminado")
    finally:
        listener.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
