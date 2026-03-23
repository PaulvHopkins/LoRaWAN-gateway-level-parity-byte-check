
=======
---

## System Architecture

Dragino LHT65 → SX1276 Sniffer (Parity Added) → SX1276 Bitflipper → RAK Gateway → UDP Forwarder → Gateway Validation → ChirpStack → MQTT Subscriber

---

## Features
- Packet sniffing using SX1276 modules  
- XOR parity byte generation and validation  
- Bit-flipping attack simulation  
- Gateway-side filtering of corrupted payloads  
- UDP packet forwarding and processing  
- MQTT-based data monitoring and decoding  

---

## Files

### `sniffer_parity.py`
Captures LoRa packets, computes an XOR parity byte, appends it to the payload, and retransmits the enhanced packet.

### `bitflipper.py`
Receives parity-enhanced packets and simulates bit-flipping attacks by modifying payload bits before retransmission.

### `gateway.py`
Acts as a custom gateway-side validation layer. Performs parity checks, strips valid parity bytes, and forwards clean packets to ChirpStack.

### `subscriber.py`
Subscribes to MQTT uplink messages, decodes payloads, and extracts sensor data along with transmission parameters.

---

## Hardware Used
- Dragino LHT65 LoRaWAN sensor  
- 2 × SX1276 (Ra-02) LoRa modules  
- Raspberry Pi 4  
- RAK WisGate Edge Lite 2 Gateway  

---

## Technologies
- Python  
- LoRa / LoRaWAN  
- MQTT (ChirpStack)  
- UDP Packet Forwarder  
- SX127x library  

---

## How It Works

1. Sensor transmits standard LoRaWAN payload  
2. Sniffer captures packet and appends parity byte  
3. Bitflipper modifies payload to simulate attacks  
4. Gateway script checks parity:  
   - Valid → forwarded  
   - Invalid → dropped  
5. Subscriber decodes and logs received data  

---

## Example Detection Logic

- Parity = XOR of all payload bytes  
- If parity mismatch occurs → potential bit-flip detected  

---

## Purpose
This project demonstrates a lightweight alternative to traditional integrity mechanisms (e.g. MIC, HMAC) by detecting payload corruption earlier in the network at the gateway level.

---

## Notes
- Designed for experimental and educational purposes  
- Focused on detection rather than prevention  
- Works within LoRaWAN constraints (low power, small payloads)  
---

## Author
Paul Hopkins
Paul Hopkins  
MEng Electronic & Computer Engineering (IoT)  
Dublin City University  
>>>>>>> 677433b73a5a8ef4452fafb58e44f4443fb2e509
