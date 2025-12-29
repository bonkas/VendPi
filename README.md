# VendPi

## Overview
Scripts for reading data from serial ports and sending to webhooks.

## Scripts

### webrequest_send.py
Reads data from a serial port and sends it as POST requests to a webhook URL.

**Usage:**
```bash
python webrequest_send.py --url https://webhook.url --serial-port /dev/ttyUSB1 --baudrate 115200 --debug
```

**Arguments:**
- `--url` (required): Webhook URL to send POST requests to
- `--serial-port`: Serial port to read from (default: /dev/ttyUSB0)
- `--baudrate`: Baud rate for serial connection (default: 9600)
- `--username`: Username for HTTP Basic Authentication
- `--password`: Password for HTTP Basic Authentication
- `--interval`: Polling interval in seconds (default: 1)
- `--insecure`: Disable SSL certificate verification
- `--debug`: Enable real-time display of incoming serial data

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