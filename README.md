# LoRaWAN Bit-Flipping Detection using Parity and Gateway Validation
 
## Overview
 
This project implements a lightweight method for detecting bit-flipping attacks in LoRaWAN networks using a parity-based approach. The system captures LoRa packets using SX1276 transceivers, appends a parity byte, simulates bit-flip attacks, and performs validation at the gateway before forwarding data to the network server.
 
The aim is to demonstrate a low-overhead, real-time integrity check suitable for constrained IoT devices.
 
---
 
## System Architecture
 
```
Dragino LHT65 → SX1276 Sniffer (Parity Added) → SX1276 Bitflipper → RAK Gateway → UDP Forwarder → Gateway Validation → ChirpStack → MQTT Subscriber
```
 
---
 
## Setup & Prerequisites
 
### pySX127x Library
 
The SX1276 radio scripts depend on the `pySX127x` library. Clone the following repository onto your Raspberry Pi:
 
```
https://github.com/rpsreal/pySX127x
```
 
Ensure the library is accessible to your Python scripts (e.g. place it in the same directory or add it to your `PYTHONPATH`).
 
### ChirpStack Docker Configuration
 
This project uses ChirpStack deployed via Docker. Two configuration changes are required before the system will work correctly.
 
#### 1. UDP Port Mapping in `docker-compose.yml`
 
The default ChirpStack Docker Compose file maps UDP port `1700:1700` for the Semtech UDP Packet Forwarder. Because the custom `gateway.py` validation layer sits between the RAK gateway and ChirpStack, you need to change the host-side port so that ChirpStack listens on a different port while the gateway script receives packets on `1700`:
 
Change:
 
```yaml
ports:
  - "1700:1700/udp"
```
 
To:
 
```yaml
ports:
  - "1701:1700/udp"
```
 
This allows `gateway.py` to bind to UDP port `1700` (receiving packets from the RAK gateway) and forward validated packets to ChirpStack on port `1701`.
 
#### 2. Region Configuration — `region_eu868.toml`
 
Edit the ChirpStack EU868 region configuration file:
 
```
chirpstack-docker/configuration/chirpstack/region_eu868.toml
```
 
Make the following changes:
 
- **Disable ADR (Adaptive Data Rate):** ADR must be disabled so that ChirpStack does not dynamically change the device's transmission parameters. The SX1276 sniffer operates on a fixed frequency and spreading factor, so ADR adjustments would cause packets to be missed.
 
- **Restrict to a single channel (868.1 MHz):** Disable all channels except `868.1 MHz`. The SX1276 sniffer listens on a single fixed frequency, so all uplinks must be transmitted on that channel for the system to function. Restricting to one channel ensures the Dragino sensor always transmits where the sniffer is listening.
 
Refer to the [ChirpStack region configuration documentation](https://www.chirpstack.io/docs/chirpstack/configuration/region.html) for the exact TOML syntax for disabling ADR and configuring channel plans.
 
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
 
Acts as a custom gateway-side validation layer. Intercepts Semtech UDP traffic between the RAK gateway and ChirpStack, performs parity checks on uplink payloads, strips valid parity bytes, and forwards clean packets to ChirpStack. Also relays PULL_RESP downlink packets (join-accepts, MAC commands) back to the gateway to enable bidirectional communication.
 
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
   - Valid → forwarded to ChirpStack
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
MEng Electronic & Computer Engineering (IoT)
Dublin City University
 
