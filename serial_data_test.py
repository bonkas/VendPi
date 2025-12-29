# Script to accept data from /dev/ttyUSB0 and send it as a POST request to a specified URL
import serial
import requests
import time
import sys
import argparse
import logging
import signal
from datetime import datetime, timezone
import json
import os
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
    parser.add_argument('--interval', type=int, default=5, help='Interval in seconds between reads.')
    parser.add_argument('--serial-port', default='/dev/ttyUSB0', help='Serial port to read from.')
    parser.add_argument('--baudrate', type=int, default=9600, help='Baud rate for the serial connection.')
    parser.add_argument('--insecure', action='store_true', help='Disable SSL certificate verification.')
    return parser.parse_args()
def main():
    args = parse_arguments()
    auth = None
    if args.username and args.password:
        auth = HTTPBasicAuth(args.username, args.password)
    try:
        ser = serial.Serial(port=args.serial_port, baudrate=args.baudrate, timeout=1)
        logging.info(f"Opened serial port {args.serial_port} at {args.baudrate} baud.")
    except SerialException as e:
        logging.error(f"Failed to open serial port: {e}")
        sys.exit(1)
    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                if line:
                    data = {
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'data': line
                    }
                    headers = {'Content-Type': 'application/json'}
                    logging.info(f"Sending data: {data}")
                    response = requests.post(
                        args.url,
                        data=json.dumps(data),
                        headers=headers,
                        auth=auth,
                        verify=not args.insecure,
                        timeout=10
                    )
                    response.raise_for_status()
                    logging.info(f"Data sent successfully. Server responded with status code {response.status_code}.")
            time.sleep(args.interval)
        except RequestException as e:
            logging.error(f"HTTP request failed: {e}")
        except SerialException as e:
            logging.error(f"Serial communication error: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
