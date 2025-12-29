# VendPi

## Overview
Scripts for reading data from serial ports and sending to webhooks.

## Purpose
This project converts a legacy vending machine that originally sent SMS messages into a system that triggers an email via a webhook. The machine communicates through a 3G serial modem using AT commands. We detect when a full message has been transmitted, capture it, and forward the data to a webhook that handles email delivery.

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

The machine issues AT commands to open the modem session and send the payload. This project uses those AT markers to detect the start and end of a message, then posts the captured content to a webhook for email processing.

## Scripts

### webrequest_send.py
Reads data from a serial port and sends it as POST requests to a webhook URL.

**Usage:**
```bash
python webrequest_send.py --url https://webhook.url \
	--serial-port /dev/ttyUSB1 --baudrate 115200 \
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

**How detection works:**
- Start when a line contains the start marker (default `AT+WOPEN`).
- Collect all subsequent lines until a line contains the end marker (default `AT+CMGR`).
- If a new start marker appears mid-collection, reset the buffer to avoid mixing packets.
- Idle timeout (`--packet-timeout`): if no new lines arrive while collecting for N seconds, send the partial packet.
- Max duration (`--max-packet-duration`): absolute cap from first start; send even if lines keep arriving.
- Optional sanitization: `--strip-nulls` removes `\x00` before decoding/processing.

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
python serial_data_test.py --serial-port /dev/ttyUSB1 --baudrate 115200
```

### send_test_data.py
Send test data to a serial port for testing purposes.

**Usage:**
```bash
python send_test_data.py --serial-port /dev/ttyUSB1 --baudrate 115200
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
	python webrequest_send.py --url https://webhook.url --serial-port /dev/pts/2 --baudrate 115200
	```

4. **In another terminal, send test data**:
	```bash
	python send_test_data.py --serial-port /dev/pts/3 --baudrate 115200
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
	python serial_data_test.py --serial-port /dev/ttyUSB1 --baudrate 115200
	```
	This will show raw bytes, decoded text, and cleaned data for debugging.

4. **Verify baud rate**: Make sure the baud rate matches your device (common rates: 9600, 115200)