"""VendPi serial packet collector → webhook sender.

Purpose:
- Replace a legacy 3G/SMS modem with a Raspberry Pi reading RS‑232 serial.
- Detect message boundaries using configurable start/end markers.
- Post captured packets as JSON to a webhook for downstream processing (e.g., email via n8n).

See README.md for:
- Sample message format and hardware setup
- All CLI parameters with defaults
- Virtual serial port testing and troubleshooting
"""

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
    parser = argparse.ArgumentParser(description='Read from a serial port and send captured packets as POST requests.')
    parser.add_argument('--url', required=True, help='The URL to send POST requests to.')
    parser.add_argument('--username', help='Username for HTTP Basic Authentication.')
    parser.add_argument('--password', help='Password for HTTP Basic Authentication.')
    # Loop tuning: small sleep to avoid CPU spin but keep responsiveness
    parser.add_argument('--interval', type=float, default=0.01, help='Loop sleep to reduce CPU usage (seconds). Default: 0.01')
    parser.add_argument('--serial-port', default='/dev/ttyUSB0', help='Serial port to read from.')
    parser.add_argument('--baudrate', type=int, default=9600, help='Baud rate for the serial connection.')
    parser.add_argument('--insecure', action='store_true', help='Disable SSL certificate verification.')
    parser.add_argument('--debug', action='store_true', help='Enable real-time display of incoming serial data.')
    parser.add_argument('--start-marker', default='AT+WOPEN', help='Substring that indicates the start of a packet. Default: AT+WOPEN')
    parser.add_argument('--end-marker', default='ATH', help='Substring that indicates the end of a packet. Default: ATH')
    # Timeouts
    # packet-timeout: Idle-based. If we are collecting and no new line arrives for this many seconds, send whatever we have.
    parser.add_argument('--packet-timeout', type=float, default=5.0, help='Idle timeout (seconds). If no new lines arrive for this duration while collecting, send the current packet. Default: 2.0')
    # max-packet-duration: Absolute cap. Even if lines keep arriving, do not collect longer than this many seconds from start.
    parser.add_argument('--max-packet-duration', type=float, default=30.0, help='Absolute maximum duration (seconds) from start-marker to send. Prevents runaway packets if end-marker never arrives. Default: 10.0')
    parser.add_argument('--strip-nulls', action='store_true', help='Remove null bytes (\\x00) from input before processing.')
    return parser.parse_args()

def main():
    args = parse_arguments()

    auth = HTTPBasicAuth(args.username, args.password) if args.username and args.password else None

    try:
        ser = serial.Serial(
            port=args.serial_port, 
            baudrate=args.baudrate, 
            timeout=0.1,
            rtscts=False,
            dsrdtr=False
        )
        logging.info(f"Opened serial port {args.serial_port} at {args.baudrate} baud.")
        if args.debug:
            logging.info(f"[DEBUG] Port settings - timeout: {ser.timeout}, rtscts: {ser.rtscts}, dsrdtr: {ser.dsrdtr}")
    except SerialException as e:
        logging.error(f"Failed to open serial port: {e}")
        sys.exit(1)

    buffer = []
    collecting = False
    started_at = None
    last_activity = None
    heartbeat_last = 0.0

    while True:
        try:
            if ser.in_waiting > 0:
                raw_bytes = ser.readline()
                if args.debug:
                    logging.info(f"[RAW BYTES] {raw_bytes}")
                decoded = raw_bytes.decode('utf-8', errors='ignore')
                if args.strip_nulls:
                    decoded = decoded.replace('\x00', '')
                line = decoded.rstrip("\r\n")

                if args.debug and (line or decoded):
                    logging.info(f"[SERIAL] '{line}'")

                if not line:
                    # Ignore empty lines
                    pass
                else:
                    # State machine for packet detection
                    if not collecting:
                        # Look for start marker anywhere in line
                        if args.start_marker in line:
                            collecting = True
                            started_at = time.time()
                            last_activity = started_at
                            buffer = [line]
                            if args.debug:
                                logging.info("[PACKET] Start detected")
                        else:
                            # Not part of packet; ignore or log
                            if args.debug:
                                logging.info("[PACKET] Not started; ignoring line")
                    else:
                        # Already collecting
                        # If another start marker appears, reset packet to avoid mixing
                        if args.start_marker in line:
                            buffer = [line]
                            started_at = time.time()
                            last_activity = started_at
                            if args.debug:
                                logging.info("[PACKET] Restart detected; buffer reset")
                        else:
                            buffer.append(line)
                            last_activity = time.time()

                        # End condition
                        if args.end_marker in line:
                            # Build and send full packet
                            full_message = "\n".join(buffer)
                            payload = {
                                'timestamp': datetime.now(timezone.utc).isoformat(),
                                'data': full_message
                            }
                            headers = {'Content-Type': 'application/json'}

                            logging.info("Sending packet:\n" + full_message)
                            try:
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
                            except RequestException as e:
                                logging.error(f"HTTP request failed: {e}")

                            # Reset state after send
                            buffer = []
                            collecting = False
                            started_at = None
                            last_activity = None

                # Debug heartbeat: log remaining idle timeout while collecting
                if collecting and last_activity and args.debug:
                    now = time.time()
                    remaining = max(0.0, args.packet_timeout - (now - last_activity))
                    # Log at ~0.5s intervals to avoid spam
                    if now - heartbeat_last >= 0.5:
                        logging.info(f"[IDLE] remaining {remaining:.2f}s, buffer size {len(buffer)}")
                        heartbeat_last = now

                # Idle timeout flush: if no new lines for too long without end marker
                if collecting and last_activity and (time.time() - last_activity > args.packet_timeout):
                    full_message = "\n".join(buffer)
                    payload = {
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'data': full_message
                    }
                    headers = {'Content-Type': 'application/json'}

                    logging.info("Idle timeout reached. Sending partial packet:\n" + full_message)
                    try:
                        response = requests.post(
                            args.url,
                            data=json.dumps(payload),
                            headers=headers,
                            auth=auth,
                            verify=not args.insecure,
                            timeout=10
                        )
                        response.raise_for_status()
                        logging.info(f"Partial packet sent (HTTP {response.status_code})")
                    except RequestException as e:
                        logging.error(f"HTTP request failed: {e}")

                    buffer = []
                    collecting = False
                    started_at = None
                    last_activity = None

                # Max duration flush: absolute cap from first start
                if collecting and started_at and (time.time() - started_at > args.max_packet_duration):
                    full_message = "\n".join(buffer)
                    payload = {
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'data': full_message
                    }
                    headers = {'Content-Type': 'application/json'}

                    logging.info("Max packet duration reached. Sending packet:\n" + full_message)
                    try:
                        response = requests.post(
                            args.url,
                            data=json.dumps(payload),
                            headers=headers,
                            auth=auth,
                            verify=not args.insecure,
                            timeout=10
                        )
                        response.raise_for_status()
                        logging.info(f"Packet sent (HTTP {response.status_code}) due to max duration")
                    except RequestException as e:
                        logging.error(f"HTTP request failed: {e}")

                    buffer = []
                    collecting = False
                    started_at = None
                    last_activity = None

            # Small sleep to avoid CPU spinning; keep loop responsive
            time.sleep(args.interval)

        except RequestException as e:
            logging.error(f"HTTP request failed: {e}")

        except SerialException as e:
            logging.error(f"Serial communication error: {e}")

        except Exception as e:
            logging.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
