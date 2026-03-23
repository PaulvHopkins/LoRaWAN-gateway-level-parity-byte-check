#!/usr/bin/env python3
import socket
import json
import struct
import base64
from datetime import datetime

UDP_PORT_receive = 1700
UDP_PORT_send = 1701
ip = "172.29.226.146"
Setup_Mode = True

PUSH_DATA = 0x00
PULL_DATA = 0x02
PUSH_ACK  = 0x01
PULL_ACK  = 0x04
TX_ACK    = 0x05

# Main socket — listens for RAK gateway
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", UDP_PORT_receive))
sock.settimeout(0.1)
print(f"Listening on port {UDP_PORT_receive}...")

# Persistent forward socket — stays open so bridge can send ACKs back
fwd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
fwd_sock.bind(("0.0.0.0", 0))
fwd_sock.settimeout(0.1)

def print_data(pkt):
    raw = base64.b64decode(pkt.get("data", ""))
    devaddr = raw[1:5][::-1].hex()
    fcnt    = struct.unpack_from("<H", raw, 6)[0]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"  Time:    {timestamp}")
    print(f"  Freq:    {pkt.get('freq')} MHz")
    print(f"  SF:      {pkt.get('datr')}")
    print(f"  Payload: {raw.hex()}")
    print(f"  DevAddr: {devaddr}")
    print(f"  FCnt:    {fcnt}")
    print(f"  Payload Length: {len(raw)} bytes")

def parity_check(payload):
    payload_bytes = base64.b64decode(payload)
    data = payload_bytes[:-1]
    parity_byte = payload_bytes[-1]
    computed = 0
    print("Performing parity check on the payload...")
    print(f"received parity: {parity_byte:02X}")
    for b in data:
        computed ^= (b & 0xFF)
    print(f"computed parity: {computed:02X}")
    return computed == parity_byte, computed, parity_byte

def sendChirp(stripped_raw, pkt):
    print("entering chirpsend")
    stripped_b64 = base64.b64encode(stripped_raw).decode()

    patched_pkt = dict(pkt)
    patched_pkt["data"] = stripped_b64
    patched_pkt["size"] = len(stripped_raw)

    json_payload = json.dumps({"rxpk": [patched_pkt]}).encode()
    gw_eui_bytes = bytes.fromhex("ac1f09fffe1bc275")
    token = struct.pack(">H", 0xABCD)
    header = bytes([0x02]) + token + bytes([PUSH_DATA]) + gw_eui_bytes

    fwd_sock.sendto(header + json_payload, (ip, UDP_PORT_send))
    print(f"  Sent to 172.0.0.1:{UDP_PORT_send}")

try:
    while True:

        # ── Uplink: RAK → proxy ───────────────────────────────────────────
        try:
            data, addr = sock.recvfrom(4096)
        except socket.timeout:
            data = None

        if data:
            version  = data[0]
            token    = data[1:3]
            pkt_type = data[3]

            if pkt_type == PUSH_DATA:
                sock.sendto(bytes([version]) + token + bytes([PUSH_ACK]), addr)

                gw_eui = data[4:12].hex()
                print(f"\nGateway: {gw_eui}")

                try:
                    json_body = json.loads(data[12:])
                except Exception:
                    continue

                for pkt in json_body.get("rxpk", []):
                    raw = base64.b64decode(pkt.get("data", ""))

                    if len(raw) == 23:  # Join Request
                        print("  Join Request — forwarding")
                        print_data(pkt)
                        sendChirp(raw, pkt)

                    elif len(raw) == 24:
                        print("  Original payload — ignoring (waiting for parity copy)")
                        if Setup_Mode:
                            sendChirp(raw, pkt)
                            Setup_Mode = False
                        print_data(pkt)

                    elif len(raw) == 25:
                        print("  Parity payload received")
                        print_data(pkt)
                        parity_valid, computed, parity_byte = parity_check(pkt.get("data", ""))
                        if not parity_valid:
                            print("  Parity check failed! Ignoring payload.")
                            print(f"  Computed parity: {computed:02X}")
                            print(f"  Received parity: {parity_byte:02X}")
                        else:
                            print("  Parity check passed! Stripping and forwarding.")
                            sendChirp(raw[:-1], pkt)

                    else:
                        print(f"  Unexpected length {len(raw)} — ignoring")

            elif pkt_type == PULL_DATA:
                sock.sendto(bytes([version]) + token + bytes([PULL_ACK]), addr)
                fwd_sock.sendto(data, (ip, UDP_PORT_send))

            elif pkt_type == TX_ACK:
                fwd_sock.sendto(data, (ip, UDP_PORT_send))
                print(f"  TX_ACK — relayed to bridge")

        # ── ACKs from bridge ──────────────────────────────────────────────
        try:
            down_data, _ = fwd_sock.recvfrom(4096)
        except socket.timeout:
            down_data = None

        if down_data and len(down_data) >= 4:
            if down_data[3] == PUSH_ACK:
                pass  # expected ACK for uplink forwards
            elif down_data[3] == PULL_ACK:
                pass  # expected ACK for relayed PULL_DATA

except KeyboardInterrupt:
    print("\nDoing a graceful termination...")

finally:
    sock.close()
    fwd_sock.close()
    print("Sockets closed. Bye!")