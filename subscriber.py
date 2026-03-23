import json
import base64
from datetime import datetime, timezone
from paho.mqtt import client as mqtt

MQTT_HOST = "localhost"
MQTT_PORT = 1883

DEV_EUI_TARGET = "a8404107f45cb2a5"
TOPIC = f"application/+/device/{DEV_EUI_TARGET}/event/up"

def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"Connected, subscribing to: {TOPIC}")
    client.subscribe(TOPIC)

def parse_sf_and_freq(j):
    """Extract spreading factor and frequency from txInfo or rxInfo."""
    sf = None
    freq = None

    tx = j.get("txInfo", {})
    freq = tx.get("frequency") or tx.get("freq")


    mod = tx.get("modulation", {})
    lora = mod.get("lora", {})
    sf = lora.get("spreadingFactor")


def decode_lht65n(data_bytes):
    if len(data_bytes) < 7:
        return {}

    bat_raw = int.from_bytes(data_bytes[0:2], "big", signed=False)
    bat_mv = bat_raw & 0x3FFF
    bat_v = bat_mv / 1000.0

    temp_raw = int.from_bytes(data_bytes[2:4], "big", signed=True)
    temp_c = temp_raw / 100.0

    hum_raw = int.from_bytes(data_bytes[4:6], "big", signed=False)
    hum_pct = hum_raw / 10.0

    return {
        "battery_v": bat_v,
        "temperature_c": temp_c,
        "humidity_pct": hum_pct,
        "payload_len": len(data_bytes),
    }

def on_message(client, userdata, msg):
    j = json.loads(msg.payload.decode("utf-8"))
    dev_eui = j.get("deviceInfo", {}).get("devEui", "")
    fcnt = j.get("fCnt", j.get("fCntUp", ""))
    data_b64 = j.get("data", "")
    data_bytes = base64.b64decode(data_b64) if data_b64 else b""
    sf, freq = parse_sf_and_freq(j)

    print(f"UP devEui={dev_eui} fcnt={fcnt} payload_hex={data_bytes.hex()} timestamp={ts}")
    print(f"   SF={sf_str}  freq={freq_mhz}")
    decoded = decode_lht65n(data_bytes)
    print("   Decoded payload:", decoded)

def main():
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.on_connect = on_connect
    c.on_message = on_message
    c.connect(MQTT_HOST, MQTT_PORT, 60)
    c.loop_forever()

if __name__ == "__main__":
    main()

