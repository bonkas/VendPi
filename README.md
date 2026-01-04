# VendPi

## Overview
Scripts for bridging a vending machine's serial output to modern web services. The Raspberry Pi reads the machine's serial data and forwards complete messages to a webhook, where an external workflow (e.g., n8n) parses the content and sends an email.

## Purpose
This project replaces the machine's aging 3G/SMS modem with a Raspberry Pi connected to the serial port. As 3G service is retired, the Pi acts as a drop-in replacement: it listens to the same AT-command driven serial traffic, extracts the meaningful message, and posts it to a webhook so an external service can deliver the content via email.

External processing is intentionally decoupled. We use n8n in our setup to split the data and send emails, but any workflow engine or webhook consumer can be used.

## Sample Message
The data we care about looks like this:

```
AT+WOPEN=0
ATE0
AT
AT+CMGS=<redacted>
07/11/25 - 14:40
SN NUMBER:<redacted>
TEMP         5.3
LITRI 265159.467
EURO    60544.50
AT+CMGD=1,4
ATH
AT+CMGR=1
```

The machine issues AT commands to open a modem session and send the payload. This project uses those AT markers to detect the start and end of a message, then posts the captured content to a webhook for downstream processing (such as emailing).

## Scripts

### webrequest_send.py
Reads data from a serial port and sends it as POST requests to a webhook URL.

**Usage:**
```bash
python webrequest_send.py --url https://webhook.url \
	--serial-port /dev/ttyUSB1 --baudrate 9600 \
	--start-marker "AT+WOPEN" --end-marker "AT+CMGR" \
	--packet-timeout 2.0 --max-packet-duration 10.0 \
	--strip-nulls --debug
```

**Arguments:**
- `--url` (required): Webhook URL to send POST requests to
- `--serial-port`: Serial port to read from. Default: /dev/ttyUSB0
- `--baudrate`: Baud rate for serial connection. Default: 9600
- `--username`: Username for HTTP Basic Authentication
- `--password`: Password for HTTP Basic Authentication
- `--insecure`: Disable SSL certificate verification
- `--interval`: Loop sleep in seconds to reduce CPU usage. Default: 0.01
- `--debug`: Enable real-time display of incoming serial data
- `--start-marker`: Substring indicating the start of a packet. Default: `AT+WOPEN`
- `--end-marker`: Substring indicating the end of a packet. Default: `AT+CMGR`
- `--packet-timeout`: Idle timeout (seconds). If no new lines arrive for this duration while collecting, the current packet is sent. Default: 2.0
- `--max-packet-duration`: Absolute maximum duration (seconds) from the first start-marker to send, even if lines keep arriving. Prevents runaway packets when the end-marker is missing. Default: 10.0
- `--strip-nulls`: Remove null bytes (\x00) before processing
- `--cooldown`: Cooldown period (seconds) after sending a packet during which incoming data is ignored. Helps prevent duplicate messages. Default: 2.0

**How detection works:**
- Start when a line contains the start marker (default `AT+WOPEN`).
- Collect all subsequent lines until a line contains the end marker (default `AT+CMGR`).
- If a new start marker appears mid-collection, reset the buffer to avoid mixing packets.
- Idle timeout (`--packet-timeout`): if no new lines arrive while collecting for N seconds, send the partial packet.
- Max duration (`--max-packet-duration`): absolute cap from first start; send even if lines keep arriving.
- Optional sanitization: `--strip-nulls` removes `\x00` before decoding/processing.

**Cooldown mechanism:**
- After a packet is successfully sent, a cooldown period begins (default: 2.0 seconds, configurable via `--cooldown`).
- During the cooldown period, all incoming serial data is dropped and ignored.
- This prevents duplicate messages that sometimes occur when serial data arrives twice.
- The cooldown applies to all packet send scenarios: normal completion, idle timeout, and max duration.
- When `--debug` is enabled, dropped data is logged with remaining cooldown time.
- To disable cooldown, use `--cooldown 0`.

**Webhook payload:**
The script posts JSON to the webhook:

```json
{
	"timestamp": "2025-01-19T13:45:10.251Z",
	"data": "AT+WOPEN=0\nATE0\nAT\nAT+CMGS=<redacted>\n...\nAT+CMGR=1"
}
```

### serial_data_test.py
Monitor and display incoming serial port data in real-time for troubleshooting.

**Usage:**
```bash
python serial_data_test.py --serial-port /dev/ttyUSB1 --baudrate 9600
```

### send_test_data.py
Send test data to a serial port for testing purposes.

**Usage:**
```bash
python send_test_data.py --serial-port /dev/ttyUSB1 --baudrate 9600
```

## Testing with Virtual Serial Ports

You can test the scripts without physical hardware using virtual serial port pairs.

### Linux/WSL

1. **Install socat** (if not already installed):
	```bash
	sudo apt-get install socat
	```

2. **Create a virtual serial port pair**:
	```bash
	socat -d -d pty,raw,echo=0 pty,raw,echo=0
	```
   
	This will output something like:
	```
	2025/12/29 21:00:00 socat[12345] N PTY is /dev/pts/2
	2025/12/29 21:00:00 socat[12345] N PTY is /dev/pts/3
	```

3. **In one terminal, run your receiver script**:
	```bash
	python webrequest_send.py --url https://webhook.url --serial-port /dev/pts/2 --baudrate 9600
	```

4. **In another terminal, send test data**:
	```bash
	python send_test_data.py --serial-port /dev/pts/3 --baudrate 9600
	```

The data sent to `/dev/pts/3` will appear on `/dev/pts/2` and be processed by your script.

### Alternative: Direct bash testing

You can also send test data directly using bash:
```bash
printf "AT+WOPEN=0\r\nATE0\r\nAT\r\nAT+CMGS=<redacted>\r\n07/11/25 - 14:40\r\nSN NUMBER:017196\r\nTEMP         5.3\r\nLITRI 265159.467\r\nEURO    60544.50\r\nAT+CMGD=1,4\r\nATH\r\nAT+CMGR=1\r\n" > /dev/pts/3
```

## Troubleshooting

### No data appearing from serial port

1. **Verify the correct serial port**:
	```bash
	ls -la /dev/ttyUSB*
	```

2. **Check permissions**:
	```bash
	sudo usermod -a -G dialout $USER
	# Log out and back in for changes to take effect
	```

3. **Use the test monitor script**:
	```bash
	python serial_data_test.py --serial-port /dev/ttyUSB1 --baudrate 9600
	```
	This will show raw bytes, decoded text, and cleaned data for debugging.

4. **Verify baud rate**: Make sure the baud rate matches your device (common rates: 9600, 115200)

## Files
- README.md: Project documentation, setup, testing, and troubleshooting.
- webrequest_send.py: Reads serial, detects packets via start/end markers, applies idle timeout and max duration, and posts JSON to a webhook.
- serial_data_test.py: Real-time serial monitor that prints raw bytes, decoded text, and cleaned lines for troubleshooting.
- send_test_data.py: Sends test lines with CRLF and a configurable delay to a serial port to simulate device output.
- sample_data.txt: Example captured serial output for reference/testing.

## Hardware Setup

Two common ways to connect the Raspberry Pi to the vending machine's serial interface:

### Option A: USB-to-Serial Adapter (Recommended)
- Use a reputable USB–RS‑232 adapter. Adapter tested: Unitek BF‑810Y (RS‑232).
- Many vending machines expose RS‑232 via a standard DB9 connector.
- Cable type matters:
	- If the vending machine presents a DTE port (like a PC), use a null‑modem (cross‑over) cable between the adapter and the machine.
	- If it presents a DCE port (like a modem), use a straight‑through cable.
- Connect the adapter to the Pi’s USB port; the device will appear as `/dev/ttyUSB0`, `/dev/ttyUSB1`, etc.
- Verify the port:
	```bash
	ls -la /dev/ttyUSB*
	dmesg | grep -i tty
	```
- Baud rate: this project uses 9600 in production (recently verified; using 115200 produced only null bytes/break conditions).
 - Project-specific note: this vending machine is DTE, so a null‑modem (cross‑over) cable is required.
- Run the receiver with the detected port:
	```bash
	python webrequest_send.py --url https://webhook.url --serial-port /dev/ttyUSB1 --baudrate 9600 --debug
	```

#### Cable selection tips
- For this project: the machine is DTE → use a null‑modem (cross‑over) cable.
- If you’re unsure whether another machine is DTE or DCE, try a straight‑through cable first; if you see no data, try a null‑modem cable.
- Symptom of wrong cable: port opens fine, but no incoming data appears in the monitor.
- Some machines label the DB9; if labeled “DTE”, use null‑modem. If labeled “DCE”, use straight‑through.

### Option B: Raspberry Pi GPIO UART (Advanced)
- Only use this if the vending machine outputs TTL (3.3V) UART. If it’s RS‑232 (±12V), add a level shifter (e.g., MAX3232) between the machine and the Pi GPIO.
- Wiring (TTL UART):
	- Pi `GPIO14` (TXD) ↔ Device RX
	- Pi `GPIO15` (RXD) ↔ Device TX
	- Common GND ↔ Device GND
	- Never connect RS‑232 signals directly to GPIO without a level shifter.
- Enable UART on the Pi:
	```bash
	sudo raspi-config
	# Interface Options → Serial → Disable login shell over serial, Enable serial port hardware
	```
- The UART device appears as `/dev/serial0` (symlink to `/dev/ttyAMA0` or `/dev/ttyS0` depending on model):
	```bash
	ls -la /dev/serial0
	```
- Run the receiver using the GPIO UART:
	```bash
	python webrequest_send.py --url https://webhook.url --serial-port /dev/serial0 --baudrate 9600 --debug
	```

### Notes & Safety
- Determine signal type before wiring: RS‑232 (±12V) vs TTL (3.3V). RS‑232 requires an adapter or level shifter.
- Share ground between devices; avoid ground loops and long unshielded runs.
- Confirm baud rate and framing (e.g., 8N1). For this machine 9600 works; typical rates are 9600 or 115200.
- On Linux, ensure the `dialout` group membership for serial access:
	```bash
	sudo usermod -a -G dialout $USER
	# Log out and back in
	```