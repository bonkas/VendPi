# VendPi

## Table of Contents
- [Overview](#overview)
- [Purpose](#purpose)
- [Files](#files)
- [Sample Message](#sample-message)
- [Hardware Setup](#hardware-setup)
- [Persistent Device Name with udev Rules](#persistent-device-name-with-udev-rules)
- [Scripts](#scripts)
- [Running as a Systemd Service](#running-as-a-systemd-service)
- [Testing with Virtual Serial Ports](#testing-with-virtual-serial-ports)
- [Troubleshooting](#troubleshooting)
- [To-Do / Future Enhancements](#to-do--future-enhancements)

## Overview
Scripts for bridging a vending machine's serial output to modern web services. The Raspberry Pi reads the machine's serial data and forwards complete messages to a webhook, where an external workflow (e.g., n8n) parses the content and sends an email.

## Purpose
This project replaces the machine's aging 3G/SMS modem with a Raspberry Pi connected to the serial port. As 3G service is retired, the Pi acts as a drop-in replacement: it listens to the same AT-command driven serial traffic, extracts the meaningful message, and posts it to a webhook so an external service can deliver the content via email.

External processing is intentionally decoupled. We use n8n in our setup to split the data and send emails, but any workflow engine or webhook consumer can be used.

## Files
- **README.md** - Project documentation, setup, testing, and troubleshooting.
- **webrequest_send.py** - Reads serial, detects packets via start/end markers, applies idle timeout and max duration, and posts JSON to a webhook.
- **serial_data_test.py** - Real-time serial monitor that prints raw bytes, decoded text, and cleaned lines for troubleshooting.
- **send_test_data.py** - Sends test lines with CRLF and a configurable delay to a serial port to simulate device output.
- **sample_data.txt** - Example captured serial output for reference/testing.

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

## Hardware Setup

Two common ways to connect the Raspberry Pi to the vending machine's serial interface:

### Option A: USB-to-Serial Adapter (Recommended)
- Use a reputable USB–RS‑232 adapter. Adapter tested: Unitek BF‑810Y (RS‑232).
- Many vending machines expose RS‑232 via a standard DB9 connector.
- Cable type matters:
	- If the vending machine presents a DTE port (like a PC), use a null‑modem (cross‑over) cable between the adapter and the machine.
	- If it presents a DCE port (like a modem), use a straight‑through cable.
- Connect the adapter to the Pi's USB port; the device will appear as `/dev/ttyUSB0`, `/dev/ttyUSB1`, etc.
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
- If you're unsure whether another machine is DTE or DCE, try a straight‑through cable first; if you see no data, try a null‑modem cable.
- Symptom of wrong cable: port opens fine, but no incoming data appears in the monitor.
- Some machines label the DB9; if labeled "DTE", use null‑modem. If labeled "DCE", use straight‑through.

### Option B: Raspberry Pi GPIO UART (Advanced)
- Only use this if the vending machine outputs TTL (3.3V) UART. If it's RS‑232 (±12V), add a level shifter (e.g., MAX3232) between the machine and the Pi GPIO.
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

## Persistent Device Name with udev Rules

USB-to-serial adapters can appear as `/dev/ttyUSB0`, `/dev/ttyUSB1`, etc., depending on the order they're detected or which USB port is used. A udev rule creates a consistent symlink (e.g., `/dev/vendpi`) that always points to your adapter.

### 1. Find your device attributes

Plug in your USB-to-serial adapter and identify it:
```bash
ls -la /dev/ttyUSB*
```

Get the device attributes (replace `ttyUSB0` with your device):
```bash
udevadm info -a -n /dev/ttyUSB0 | grep -E '{idVendor}|{idProduct}|{serial}|{manufacturer}|{product}'
```

Example output:
```
ATTRS{idProduct}=="23a3"
ATTRS{idVendor}=="067b"
ATTRS{manufacturer}=="Prolific Technology Inc. "
ATTRS{product}=="USB-Serial Controller "
ATTRS{serial}=="BXDYb119D15"
```

Note the `idVendor`, `idProduct`, and `serial` values for your adapter.

### 2. Create the udev rule

Create the rule file:
```bash
sudo nano /etc/udev/rules.d/99-vendpi.rules
```

Add this rule (replace the values with your adapter's attributes):
```
# VendPi USB-to-Serial adapter (Prolific/Unitek BF-810Y)
# Creates symlink /dev/vendpi for consistent device naming
SUBSYSTEM=="tty", ATTRS{idVendor}=="067b", ATTRS{idProduct}=="23a3", ATTRS{serial}=="BXDYb119D15", SYMLINK+="vendpi", MODE="0660", GROUP="dialout"
```

**Rule breakdown:**
- `SUBSYSTEM=="tty"` - Only matches serial/tty devices
- `ATTRS{idVendor}` / `ATTRS{idProduct}` - Matches your specific adapter model
- `ATTRS{serial}` - Matches this exact adapter (useful if you have multiple of the same model)
- `SYMLINK+="vendpi"` - Creates `/dev/vendpi` symlink
- `MODE="0660"` - Sets read/write permissions for owner and group
- `GROUP="dialout"` - Assigns to dialout group for user access

### 3. Apply and test the rule

```bash
# Reload udev rules
sudo udevadm control --reload-rules

# Trigger rules for existing devices
sudo udevadm trigger

# Verify the symlink
ls -la /dev/vendpi
```

Expected output:
```
lrwxrwxrwx 1 root root 7 Jan 15 12:00 /dev/vendpi -> ttyUSB0
```

### 4. Test persistence

Unplug and replug the adapter, or plug it into a different USB port. The `/dev/vendpi` symlink should always point to your adapter.

### 5. Update your scripts and services

Use `/dev/vendpi` instead of `/dev/ttyUSB0` or `/dev/ttyUSB1`:
```bash
python webrequest_send.py --url https://webhook.url --serial-port /dev/vendpi --baudrate 9600
```

## Scripts

### webrequest_send.py
Reads data from a serial port and sends it as POST requests to a webhook URL.

**Usage:**
```bash
python webrequest_send.py --url https://webhook.url \
	--serial-port /dev/ttyUSB1 --baudrate 9600 \
	--start-marker "AT+CMGS" --end-marker "ATH" \
	--packet-timeout 5.0 --max-packet-duration 30.0 \
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
- `--start-marker`: Substring indicating the start of a packet. Default: `AT+CMGS`
- `--end-marker`: Substring indicating the end of a packet. Default: `ATH`
- `--packet-timeout`: Idle timeout (seconds). If no new lines arrive for this duration while collecting, the current packet is sent. Default: 5.0
- `--max-packet-duration`: Absolute maximum duration (seconds) from the first start-marker to send, even if lines keep arriving. Prevents runaway packets when the end-marker is missing. Default: 30.0
- `--strip-nulls`: Remove null bytes (\x00) before processing
- `--cooldown`: Cooldown period (seconds) after sending a packet during which incoming data is ignored. Helps prevent duplicate messages. Default: 120.0

**How detection works:**
- Start when a line contains the start marker (default `AT+CMGS`).
- Collect all subsequent lines until a line contains the end marker (default `ATH`).
- If a new start marker appears mid-collection, reset the buffer to avoid mixing packets.
- Idle timeout (`--packet-timeout`): if no new lines arrive while collecting for N seconds, send the partial packet.
- Max duration (`--max-packet-duration`): absolute cap from first start; send even if lines keep arriving.
- Optional sanitization: `--strip-nulls` removes `\x00` before decoding/processing.

**Cooldown mechanism:**
- After a packet is successfully sent, a cooldown period begins (configurable via `--cooldown`).
- During the cooldown period, all incoming serial data is dropped and ignored.
- This prevents duplicate messages that sometimes occur when serial data arrives twice.
- The cooldown applies to all packet send scenarios: normal completion, idle timeout, and max duration.
- When `--debug` is enabled, dropped data is logged with remaining cooldown time.
- Cooldown is enabled by default (120.0 seconds). Disable it by setting `--cooldown` to 0.

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
python send_test_data.py --serial-port /dev/ttyUSB1 --baudrate 9600 --delay 0.1
```

**Arguments:**
- `--serial-port`: Serial port to write to. Default: /dev/ttyUSB0
- `--baudrate`: Baud rate for serial connection. Default: 9600
- `--delay`: Delay between sending each line in seconds. Default: 0.1

## Running as a Systemd Service

For production deployment, run the script as a systemd service with credentials stored securely in an environment file.

### 1. Create the environment file

Store your webhook URL and credentials in `/etc/vendpi.env`:

```bash
sudo nano /etc/vendpi.env
```

Add your configuration:
```
WEBHOOK_URL=https://your-webhook.url
VENDPI_USERNAME=your_username
VENDPI_PASSWORD=your_password
```

### 2. Secure the environment file

Restrict access to root only:
```bash
sudo chown root:root /etc/vendpi.env
sudo chmod 600 /etc/vendpi.env
```

**Note:** The environment variables (`WEBHOOK_URL`, `VENDPI_USERNAME`, `VENDPI_PASSWORD`) are only loaded automatically when running as a systemd service. When running the Python script manually, you must pass `--url`, `--username`, and `--password` as command line arguments.

### 3. Create the service file

Create the systemd service unit:
```bash
sudo nano /etc/systemd/system/vendpi.service
```

Add the following configuration:
```ini
[Unit]
Description=VendPi Webhook Service
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=pi
EnvironmentFile=/etc/vendpi.env
Restart=always
RestartSec=10
ExecStart=/usr/bin/python3 /home/pi/VendPi/webrequest_send.py \
  --serial-port /dev/vendpi \
  --baudrate 9600 \
  --debug \
  --cooldown 120

# --- Security hardening ---
NoNewPrivileges=yes
ProtectSystem=strict
PrivateTmp=yes
RestrictSUIDSGID=yes
RestrictAddressFamilies=AF_INET AF_INET6
ReadOnlyPaths=/home/pi/VendPi
LogsDirectory=vendpi

[Install]
WantedBy=multi-user.target
```

### 4. Enable and start the service

```bash
# Reload systemd to pick up the new service
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable vendpi.service

# Start the service
sudo systemctl start vendpi.service
```

### 5. Managing the service

```bash
# Check service status
sudo systemctl status vendpi.service

# View logs
sudo journalctl -u vendpi.service -f

# Restart the service
sudo systemctl restart vendpi.service

# Stop the service
sudo systemctl stop vendpi.service
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

### Testing with systemd service

When testing virtual serial ports with the systemd service, you may encounter a permission denied error:

```
ERROR - Failed to open serial port: [Errno 13] could not open port /dev/pts/8: [Errno 13] Permission denied
```

**Why this happens:** Virtual serial ports created by socat are owned by the user who ran socat, with restricted permissions. The systemd service runs as the `pi` user, which doesn't have access to these ports by default.

**Solution:** Create the virtual ports with explicit user, group, and permissions:

```bash
socat -d -d pty,raw,echo=0,user=pi,group=dialout,mode=660 pty,raw,echo=0,user=pi,group=dialout,mode=660
```

This creates both ports with:
- Owner: `pi`
- Group: `dialout`
- Permissions: `660` (read/write for owner and group)

Then update your service to use the virtual port and restart:
```bash
sudo systemctl restart vendpi.service
```

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

## To-Do / Future Enhancements

- [x] **Persistent device name with udev rules** - Create a udev rule to give the USB-to-serial adapter a consistent symlink (e.g., `/dev/vendpi`) regardless of which USB port it's plugged into. See [Persistent Device Name with udev Rules](#persistent-device-name-with-udev-rules).

- [ ] **Reconnection on disconnect** - Add logic to detect when the USB-to-serial adapter is unplugged and automatically reconnect when it's plugged back in, rather than requiring a service restart.
