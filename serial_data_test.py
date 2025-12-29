# Script to monitor and display data from a serial port for troubleshooting
import serial
import time
import sys
import argparse
import logging
import signal
from datetime import datetime, timezone
from serial.serialutil import SerialException
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
def signal_handler(sig, frame):
    logging.info("Termination signal received. Exiting gracefully...")
    sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def parse_arguments():
    parser = argparse.ArgumentParser(description='Monitor serial port and display incoming data in real-time.')
    parser.add_argument('--serial-port', default='/dev/ttyUSB0', help='Serial port to read from.')
    parser.add_argument('--baudrate', type=int, default=9600, help='Baud rate for the serial connection.')
    return parser.parse_args()
def main():
    args = parse_arguments()

    try:
        ser = serial.Serial(
            port=args.serial_port, 
            baudrate=args.baudrate, 
            timeout=0.1,
            rtscts=False,
            dsrdtr=False
        )
        logging.info(f"Opened serial port {args.serial_port} at {args.baudrate} baud.")
        logging.info(f"[DEBUG] Port settings - timeout: {ser.timeout}, rtscts: {ser.rtscts}, dsrdtr: {ser.dsrdtr}")
    except SerialException as e:
        logging.error(f"Failed to open serial port: {e}")
        sys.exit(1)

    logging.info("Monitoring serial port... Press Ctrl+C to exit.")

    while True:
        try:
            if ser.in_waiting > 0:
                raw_bytes = ser.readline()
                logging.info(f"[RAW BYTES] {raw_bytes}")
                line = raw_bytes.decode('utf-8', errors='ignore').rstrip("\r\n")
                if line:
                    timestamp = datetime.now(timezone.utc).isoformat()
                    logging.info(f"[{timestamp}] {line}")
                else:
                    logging.info(f"[EMPTY LINE] After stripping")

            time.sleep(0.01)  # Small delay to prevent CPU spinning

        except SerialException as e:
            logging.error(f"Serial communication error: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
