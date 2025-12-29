# Script to accept data from /dev/ttyUSB0 and send it as a POST request to a specified URL

# v0.1 Initial functionality of script tested
# v0.2 Updated to support multiline data

# Example json to send to webhook:
#
#{
#  "timestamp": "2025-01-19T13:45:10.251Z",
#  "data": "AT+WOPEN=0\nATE0\nAT\nAT+CMGS=<redacted>\n07/11/25 - 14:40\nSN NUMBER:017196\nTEMP         5.3\nLITRI 265159.467\nEURO    60544.50\nAT+CMGD=1,4\nATH\nAT+CMGR=1"
#}
#
# Example usage to pipe data to serial port from terminal:
# printf "AT+WOPEN=0\r\nATE0\r\nAT\r\nAT+CMGS=<redacted>\r\n07/11/25 - 14:40\r\nSN NUMBER:017196\r\nTEMP         5.3\r\nLITRI 265159.467\r\nEURO    60544.50\r\nAT+CMGD=1,4\r\nATH\r\nAT+CMGR=1\r\n" \
#  > /dev/ttyUSB0

# Example usage of the script:
# python webrequest-test_v0.2.py --url https://n8n.webhook.url --username '' --password '' --serial-port /dev/ttyUSB0 --baudrate 112500

import serial
import requests
import time
import sys
import argparse
import logging
import signal
from datetime import datetime, timezone
import json
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException
from serial.serialutil import SerialException
from urllib3.exceptions import InsecureRequestWarning
from urllib3 import disable_warnings

disable_warnings(InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def signal_handler(sig, frame):
    logging.info("Termination signal received. Exiting gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def parse_arguments():
    parser = argparse.ArgumentParser(description='Read from /dev/ttyUSB0 and send data as POST requests.')
    parser.add_argument('--url', required=True, help='The URL to send POST requests to.')
    parser.add_argument('--username', help='Username for HTTP Basic Authentication.')
    parser.add_argument('--password', help='Password for HTTP Basic Authentication.')
    parser.add_argument('--interval', type=int, default=1, help='Polling interval.')
    parser.add_argument('--serial-port', default='/dev/ttyUSB0', help='Serial port to read from.')
    parser.add_argument('--baudrate', type=int, default=9600, help='Baud rate for the serial connection.')
    parser.add_argument('--insecure', action='store_true', help='Disable SSL certificate verification.')
    return parser.parse_args()

def main():
    args = parse_arguments()

    auth = HTTPBasicAuth(args.username, args.password) if args.username and args.password else None

    try:
        ser = serial.Serial(port=args.serial_port, baudrate=args.baudrate, timeout=0.1)
        logging.info(f"Opened serial port {args.serial_port} at {args.baudrate} baud.")
    except SerialException as e:
        logging.error(f"Failed to open serial port: {e}")
        sys.exit(1)

    buffer = []
    last_read = time.time()

    while True:
        try:
            if ser.in_waiting > 0:
                raw = ser.readline().decode('utf-8', errors='ignore').rstrip("\r\n")
                if raw:
                    buffer.append(raw)
                    last_read = time.time()
            # If we have all data required, send it. We can check this by looking at the first and last line of the buffer.
            if buffer and buffer[0].startswith("AT+WOPEN") and buffer[-1].startswith("AT+CMGR"):
                full_message = "\n".join(buffer)
                buffer = []  # clear buffer

                payload = {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'data': full_message
                }

                headers = {'Content-Type': 'application/json'}

                logging.info("Sending packet:\n" + full_message)

                response = requests.post(
                    args.url,
                    data=json.dumps(payload),
                    headers=headers,
                    auth=auth,
                    verify=not args.insecure,
                    timeout=10
                )
                response.raise_for_status()
                logging.info(f"Packet sent successfully (HTTP {response.status_code})")

            # If no new data for 0.2 seconds AND buffer has content → send packet
            # NO LONGER USED! Replaced with above to check for start/end lines
            """ if buffer and (time.time() - last_read > 0.2):
                full_message = "\n".join(buffer)
                buffer = []  # clear buffer

                payload = {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'data': full_message
                }

                headers = {'Content-Type': 'application/json'}

                logging.info("Sending packet:\n" + full_message)

                response = requests.post(
                    args.url,
                    data=json.dumps(payload),
                    headers=headers,
                    auth=auth,
                    verify=not args.insecure,
                    timeout=10
                )
                response.raise_for_status()
                logging.info(f"Packet sent successfully (HTTP {response.status_code})") """

            time.sleep(args.interval)

        except RequestException as e:
            logging.error(f"HTTP request failed: {e}")

        except SerialException as e:
            logging.error(f"Serial communication error: {e}")

        except Exception as e:
            logging.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
