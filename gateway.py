#!/usr/bin/env python3
import base64
import json
import os
import socket
import struct
from datetime import datetime

UDP_PORT_RECEIVE = 1700
UDP_PORT_SEND = 1701
CHIRPSTACK_IP = os.environ.get("CHIRPSTACK_UDP_IP", "172.29.226.146")
SETUP_MODE = True

PUSH_DATA = 0x00
PUSH_ACK = 0x01
PULL_DATA = 0x02
PULL_RESP = 0x03
PULL_ACK = 0x04
TX_ACK = 0x05

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", UDP_PORT_RECEIVE))
sock.settimeout(0.1)
print(f"Listening on port {UDP_PORT_RECEIVE}...")

fwd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
fwd_sock.bind(("0.0.0.0", 0))
fwd_sock.settimeout(0.1)

gateway_pull_addr = None
last_gateway_eui = None


def print_data(pkt):
    raw = base64.b64decode(pkt.get("data", ""))
    devaddr = raw[1:5][::-1].hex() if len(raw) >= 5 else "unknown"
    fcnt = struct.unpack_from("<H", raw, 6)[0] if len(raw) >= 8 else 0
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"  Time:    {timestamp}")
    print(f"  Freq:    {pkt.get('freq')} MHz")
    print(f"  SF:      {pkt.get('datr')}")
    print(f"  Payload: {raw.hex()}")
    print(f"  DevAddr: {devaddr}")
    print(f"  FCnt:    {fcnt}")
    print(f"  Payload Length: {len(raw)} bytes")


def parity_check(payload_b64):
    payload_bytes = base64.b64decode(payload_b64)
    data = payload_bytes[:-1]
    parity_byte = payload_bytes[-1]
    computed = 0
    print("Performing parity check on the payload...")
    print(f"received parity: {parity_byte:02X}")
    for byte_value in data:
        computed ^= byte_value & 0xFF
    print(f"computed parity: {computed:02X}")
    return computed == parity_byte, computed, parity_byte


def send_chirp(raw_payload, pkt, gw_eui):
    print("entering chirpsend")
    patched_pkt = dict(pkt)
    patched_pkt["data"] = base64.b64encode(raw_payload).decode()
    patched_pkt["size"] = len(raw_payload)

    json_payload = json.dumps({"rxpk": [patched_pkt]}).encode()
    token = struct.pack(">H", 0xABCD)
    header = bytes([0x02]) + token + bytes([PUSH_DATA]) + bytes.fromhex(gw_eui)

    fwd_sock.sendto(header + json_payload, (CHIRPSTACK_IP, UDP_PORT_SEND))
    print(f"  Sent to {CHIRPSTACK_IP}:{UDP_PORT_SEND}")


try:
    while True:
        try:
            data, addr = sock.recvfrom(4096)
        except socket.timeout:
            data = None

        if data:
            version = data[0]
            token = data[1:3]
            pkt_type = data[3]

            if pkt_type == PUSH_DATA:
                sock.sendto(bytes([version]) + token + bytes([PUSH_ACK]), addr)

                gw_eui = data[4:12].hex()
                last_gateway_eui = gw_eui
                print(f"\nGateway: {gw_eui}")

                try:
                    json_body = json.loads(data[12:])
                except Exception:
                    continue

                for pkt in json_body.get("rxpk", []):
                    raw = base64.b64decode(pkt.get("data", ""))

                    if len(raw) == 23:
                        print("  Join Request - forwarding")
                        print_data(pkt)
                        send_chirp(raw, pkt, gw_eui)

                    elif len(raw) == 24:
                        print("  Original payload - ignoring (waiting for parity copy)")
                        if SETUP_MODE:
                            send_chirp(raw, pkt, gw_eui)
                            SETUP_MODE = False
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
                            send_chirp(raw[:-1], pkt, gw_eui)

                    else:
                        print(f"  Unexpected length {len(raw)} - ignoring")

            elif pkt_type == PULL_DATA:
                gateway_pull_addr = addr
                last_gateway_eui = data[4:12].hex()
                sock.sendto(bytes([version]) + token + bytes([PULL_ACK]), addr)
                fwd_sock.sendto(data, (CHIRPSTACK_IP, UDP_PORT_SEND))

            elif pkt_type == TX_ACK:
                fwd_sock.sendto(data, (CHIRPSTACK_IP, UDP_PORT_SEND))
                print("  TX_ACK - relayed to bridge")

        try:
            down_data, _ = fwd_sock.recvfrom(4096)
        except socket.timeout:
            down_data = None

        if down_data and len(down_data) >= 4:
            down_type = down_data[3]
            if down_type == PUSH_ACK:
                pass
            elif down_type == PULL_ACK:
                pass
            elif down_type == PULL_RESP:
                if gateway_pull_addr is None:
                    print("  PULL_RESP received from ChirpStack but no gateway pull address is known yet.")
                else:
                    sock.sendto(down_data, gateway_pull_addr)
                    gateway_id = last_gateway_eui or "unknown"
                    print(
                        f"  PULL_RESP - relayed to gateway {gateway_id} at "
                        f"{gateway_pull_addr[0]}:{gateway_pull_addr[1]}"
                    )

except KeyboardInterrupt:
    print("\nDoing a graceful termination...")

finally:
    sock.close()
    fwd_sock.close()
    print("Sockets closed. Bye!")
