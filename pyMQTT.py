import serial
import json
import time
import os
import sys
import paho.mqtt.client as mqtt
import re

# MQTT Configuration
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "home/sensor/xbee"

# Serial Configuration
SERIAL_PORT = "/dev/ttyUSB0"  # Adjust to match your setup
BAUD_RATE = 9600

# Global Counter
message_counter = 0

# Function to restart script
def restart_script():
    print("[DEBUG] Restarting script in 5 seconds...")
    time.sleep(5)
    os.execv(sys.executable, ['python3'] + sys.argv)  # Restart script

# Initialize Serial Connection
def setup_serial():
    try:
        print("[DEBUG] Attempting to connect to serial port...")
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
        time.sleep(2)  # Allow serial connection to stabilize
        ser.reset_input_buffer()
        print(f"[DEBUG] Serial connection established on {SERIAL_PORT} at {BAUD_RATE} baud.")
        return ser
    except serial.SerialException as e:
        print(f"[ERROR] Failed to connect to serial port: {e}")
        restart_script()

# Initialize MQTT
def setup_mqtt():
    print("[DEBUG] Initializing MQTT client...")
    client = mqtt.Client()
    try:
        print(f"[DEBUG] Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        print("[DEBUG] Successfully connected to MQTT broker.")
    except Exception as e:
        print(f"[ERROR] Failed to connect to MQTT broker: {e}")
        restart_script()
    return client

# Read serial data and detect NULL bytes
def read_serial_data(ser):
    print(f"[DEBUG] Bytes in serial buffer before reading: {ser.in_waiting}")
    ser.reset_input_buffer()  # Clear the buffer before reading
    raw_data = b""
    start_time = time.time()
    while time.time() - start_time < 3:  # Limit to 3 seconds per read
        if ser.in_waiting > 0:
            byte = ser.read(1)
            raw_data += byte
            if byte == b'\n':  # Stop reading when newline is received
                break
        else:
            time.sleep(0.1)  # Prevent high CPU usage
    print(f"[DEBUG] Bytes in serial buffer after reading: {ser.in_waiting}")
    if raw_data:
        print(f"[DEBUG] Raw serial data (before decoding): {repr(raw_data)}")
        if raw_data.count(b'\x00') > len(raw_data) * 0.8:  # More than 80% NULL bytes
            print("[ERROR] Received mostly NULL bytes! Resetting serial connection...")
            return None  # Signal to restart serial
        try:
            decoded_data = raw_data.decode('utf-8', errors='ignore').strip()
            valid_data = re.sub(r'[^0-9.,-]', '', decoded_data)  # Remove unexpected characters
            print(f"[DEBUG] Decoded & cleaned data: {valid_data}")
            return valid_data
        except UnicodeDecodeError:
            print(f"[WARNING] Received non-decodable data: {repr(raw_data)}")
            return ""
    return ""

# Main Loop with Watchdog Timer
def main():
    global message_counter
    print("[DEBUG] Starting main function...")
    client = setup_mqtt()
    client.loop_start()  # Start MQTT in the background
    last_message_time = time.time()  # Watchdog timer to track last message
    try:
        print("[DEBUG] Entering main loop, listening for XBee data...")
        while True:
            try:
                # Initialize serial connection
                ser = setup_serial()
                print("[DEBUG] Checking if data is available on serial port...")
                raw_data = read_serial_data(ser)
                if raw_data is None:  # Serial reset required
                    print("[ERROR] Restarting serial connection due to NULL data...")
                    ser.close()
                    time.sleep(2)
                    continue
                if time.time() - last_message_time > 30:
                    print("[ERROR] No data received for 30 seconds, resetting serial connection...")
                    ser.close()
                    time.sleep(2)
                    continue
                if not raw_data:
                    print("[WARNING] Received empty data, retrying...")
                    ser.close()
                    time.sleep(2)
                    continue
                print(f"[DEBUG] Processing received data: {raw_data}")
                # Ensure correct format (temperature,humidity)
                parts = raw_data.split(',')
                if len(parts) != 2:
                    print(f"[WARNING] Malformed data received: {raw_data}, skipping...")
                    ser.close()
                    time.sleep(2)
                    continue
                # Unpack values
                try:
                    print("[DEBUG] Converting data to numeric format...")
                    temperature = float(parts[0])
                    humidity = float(parts[1])
                    print(f"[DEBUG] Parsed Values - Temperature: {temperature} °C, Humidity: {humidity} %")
                except ValueError:
                    print(f"[WARNING] Non-numeric data received: {raw_data}, skipping...")
                    ser.close()
                    time.sleep(2)
                    continue
                # Update watchdog timer
                last_message_time = time.time()
                # Create JSON payload
                sensor_data = {"temperature": temperature, "humidity": humidity}
                print(f"[DEBUG] JSON Payload Created: {sensor_data}")
                # Publish to MQTT
                print("[DEBUG] Publishing to MQTT...")
                client.publish(MQTT_TOPIC, json.dumps(sensor_data), qos=0, retain=True)
                # Increment and print message counter
                message_counter += 1
                print(f"[INFO] [Message Count: {message_counter}] Successfully Published to MQTT: {sensor_data}")
                # Print heartbeat message
                if message_counter % 10 == 0:
                    print(f"[INFO] [Message Count: {message_counter}] Program is running...")
            except serial.SerialException as e:
                print(f"[ERROR] Serial error: {e}, restarting serial connection...")
                ser.close()
                time.sleep(2)
            except Exception as e:
                print(f"[ERROR] Unexpected error in main loop: {e}, restarting...")
                restart_script()
            finally:
                # Reset serial connection after every read
                if 'ser' in locals():
                    ser.close()
                    print("[DEBUG] Serial connection reset after read.")
            time.sleep(2)
    except KeyboardInterrupt:
        print("[DEBUG] KeyboardInterrupt detected, stopping script...")
    finally:
        print("[DEBUG] Cleaning up resources...")
        if 'ser' in locals():
            ser.close()
        client.loop_stop()
        client.disconnect()
        print("[INFO] Resources cleaned up. Exiting.")

# Run main function
if __name__ == "__main__":
    print("[DEBUG] Running script as __main__")
    main()