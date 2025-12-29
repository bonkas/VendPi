#!/usr/bin/env python3
# Script to send test data to a serial port

import serial
import time
import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(description='Send test data to serial port.')
    parser.add_argument('--serial-port', default='/dev/ttyUSB0', help='Serial port to write to.')
    parser.add_argument('--baudrate', type=int, default=115200, help='Baud rate for the serial connection.')
    parser.add_argument('--delay', type=float, default=0.1, help='Delay between lines in seconds.')
    return parser.parse_args()

def main():
    args = parse_arguments()
    
    test_data = [
        "AT+WOPEN=0",
        "ATE0",
        "AT",
        "AT+CMGS=<redacted>",
        "07/11/25 - 14:40",
        "SN NUMBER:017196",
        "TEMP         5.3",
        "LITRI 265159.467",
        "EURO    60544.50",
        "AT+CMGD=1,4",
        "ATH",
        "AT+CMGR=1"
    ]
    
    try:
        ser = serial.Serial(port=args.serial_port, baudrate=args.baudrate, timeout=1)
        print(f"Opened serial port {args.serial_port} at {args.baudrate} baud.")
        
        print("Sending test data...")
        for line in test_data:
            ser.write((line + "\r\n").encode('utf-8'))
            print(f"Sent: {line}")
            time.sleep(args.delay)
        
        print("Test data sent successfully!")
        ser.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
