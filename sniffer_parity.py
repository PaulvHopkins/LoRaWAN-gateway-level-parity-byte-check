#!/usr/bin/env python3

import time
import RPi.GPIO as GPIO

from SX127x import LoRa
from SX127x.LoRa import MODE
from SX127x.board_config import BOARD
from SX127x.constants import BW, CODING_RATE

GPIO.setwarnings(False)

# freq setting
FREQUENCY = 868.1
SPREADING_FACTOR = 7



def get_irq_flags(lora):
    if hasattr(lora, "get_irq_flags"):
        return lora.get_irq_flags()
    if hasattr(lora, "read_irq_flags"):
        return lora.read_irq_flags()
    raise RuntimeError("No IRQ flag method found")


def flag_is_set(flags, name):
    value = flags.get(name, 0)
    if isinstance(value, bool):
        return value
    return value == 1


def has_crc_error(flags):
    return any(flags.get(k) for k in (
        "payload_crc_error", "PayloadCrcError",
        "crc_error", "RxPayloadCrcError",
    ))


def devaddr_fcnt(payload):
    dev_addr = "".join(f"{b:02x}" for b in payload[1:5][::-1])
    fcnt = payload[6] | (payload[7] << 8)
    return dev_addr, fcnt


def compute_parity(data):
    #XOR parity byte over all bytes.
    parity = 0
    for b in data:
        parity ^= (b & 0xFF)
    return parity


def transmit(lora, payload_bytes):
    #Switch to TX, send payload, wait for TxDone
    lora.set_mode(MODE.STDBY)
    time.sleep(0.01)
    lora.write_payload(list(payload_bytes))
    lora.set_mode(MODE.TX)

    t0 = time.time()
    while (time.time() - t0) < 3.0:
        flags = get_irq_flags(lora)
        if flags.get("tx_done") or flags.get("TxDone"):
            break
        time.sleep(0.005)

    lora.clear_irq_flags(TxDone=1)
    lora.set_mode(MODE.STDBY)
    # Wait for own echo to pass before returning to RX so that it doens't loop
    time.sleep(0.5)


def rx_read(lora):
    #Check if a packet arrived. Returns bytearray
    flags = get_irq_flags(lora)

    if not (flag_is_set(flags, "RxDone") or flag_is_set(flags, "rx_done")):
        return None

    lora.clear_irq_flags(RxDone=1)

    if has_crc_error(flags):
        lora.clear_irq_flags(PayloadCrcError=1)
        lora.reset_ptr_rx()
        lora.set_mode(MODE.RXCONT)
        return None

    try:
        raw = lora.read_payload(nocheck=True) or []
    except Exception as e:
        print(f"  Read error: {e}")
        lora.reset_ptr_rx()
        lora.set_mode(MODE.RXCONT)
        return None

    if not raw or len(raw) < 8:
        lora.reset_ptr_rx()
        lora.set_mode(MODE.RXCONT)
        return None

    return bytearray(raw)


def start_rx(lora):
    #Put radio into continuous receive mode.
    lora.set_mode(MODE.STDBY)
    lora.clear_irq_flags(RxDone=1, PayloadCrcError=1, TxDone=1,
                         ValidHeader=1, FhssChangeChannel=1, CadDone=1, CadDetected=1)
    lora.reset_ptr_rx()
    lora.set_mode(MODE.RXCONT)


def init_radio(board):
    #SX1276 for 868.1 MHz SF7 LoRaWAN
    LoRa.BOARD = board
    LoRa.LoRa.spi = board.SpiDev()

    lora = LoRa.LoRa(verbose=False)

    lora.set_mode(MODE.SLEEP)
    lora.set_dio_mapping([0, 0, 0, 0, 0, 0])
    lora.set_mode(MODE.STDBY)

    lora.set_freq(FREQUENCY)
    lora.set_pa_config(pa_select=1)
    lora.set_rx_crc(True)
    lora.set_sync_word(0x34)
    lora.set_spreading_factor(SPREADING_FACTOR)
    lora.set_bw(BW.BW125)
    lora.set_coding_rate(CODING_RATE.CR4_5)
    lora.set_preamble(8)
    lora.set_low_data_rate_optim(False)
    lora.set_implicit_header_mode(False)

    lora.reset_ptr_rx()
    lora.clear_irq_flags(RxDone=1, PayloadCrcError=1)

    return lora



def main():
    print("  LoRaWAN Parity Adder")
    print(f"  Frequency: {FREQUENCY} MHz  SF{SPREADING_FACTOR}")

    BOARD.setup()
    lora = init_radio(BOARD)

    packets = 0

    start_rx(lora)
    print("\nListening. Press Ctrl+C to stop.\n")

    try:
        while True:
            payload = rx_read(lora)

            if payload is not None:
                dev_addr, fcnt = devaddr_fcnt(payload)

                if dev_addr is None:
                    start_rx(lora)
                    continue

                parity = compute_parity(payload)
                enhanced = payload + bytearray([parity])

                print(f" ------------Captured packet-----------")
                print(f"  DevAddr  : {dev_addr}  FCnt: {fcnt} ")
                print(f"  Parity   : 0x{parity:02x}")
                print(f"  Payload  : {' '.join(f'{b:02x}' for b in payload)}")
           
                print(f"  Enhanced : {' '.join(f'{b:02x}' for b in enhanced)}")
                print(f"  Length   : {len(payload)} -> {len(enhanced)} bytes")

                transmit(lora, enhanced)
                packets += 1
                print(f" Retransmitted ({packets} total) ")

                start_rx(lora)

            time.sleep(0.005)

    except KeyboardInterrupt:
        print(f"\nStopping. {packets} packets retransmitted.")
    finally:
        try:
            BOARD.led_off()
        except Exception:
            pass
        lora.set_mode(MODE.SLEEP)
        BOARD.teardown()
        GPIO.cleanup()


if __name__ == "__main__":
    main()
