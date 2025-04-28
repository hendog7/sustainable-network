from multiprocessing import Process, Value
import serial
import json
import time
import os
import sys
import paho.mqtt.client as mqtt
import re

# Serial Configuration
SERIAL_PORT = "/dev/ttyUSB0"  # Adjust to match your setup
BAUD_RATE = 9600

# Global Counter
message_counter = 0

def restart_script():
    print("[DEBUG] Restarting script in 5 seconds...")
    time.sleep(5)
    os.execv(sys.executable, ['python3'] + sys.argv)

def load_mqtt_config():
    """Load MQTT configuration from a JSON file."""
    try:
        with open("MQTT-config.json", "r") as f:
            mqtt_config = json.load(f)
        if not all(k in mqtt_config for k in ["MQTT_BROKER", "MQTT_PORT", "MQTT_TOPIC"]):
            raise KeyError("Missing required MQTT configuration keys")
        return mqtt_config["MQTT_BROKER"], int(mqtt_config["MQTT_PORT"]), mqtt_config["MQTT_TOPIC"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"[ERROR] Failed to load MQTT config: {e}")
        restart_script()

def setup_serial():
    try:
        print("[DEBUG] Attempting to connect to serial port...")
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
        time.sleep(2)
        ser.reset_input_buffer()
        print(f"[DEBUG] Serial connection established on {SERIAL_PORT} at {BAUD_RATE} baud.")
        return ser
    except serial.SerialException as e:
        print(f"[ERROR] Failed to connect to serial port: {e}")
        restart_script()

def setup_mqtt():
    """Initialize MQTT with configuration from JSON file."""
    mqtt_broker, mqtt_port, mqtt_topic = load_mqtt_config()
    print("[DEBUG] Initializing MQTT client...")
    client = mqtt.Client()
    try:
        print(f"[DEBUG] Connecting to MQTT broker at {mqtt_broker}:{mqtt_port}...")
        client.connect(mqtt_broker, mqtt_port, 60)
        print("[DEBUG] Successfully connected to MQTT broker.")
    except Exception as e:
        print(f"[ERROR] Failed to connect to MQTT broker: {e}")
        restart_script()
    return client, mqtt_topic

def read_serial_data(ser):
    """Read and clean serial data."""
    ser.reset_input_buffer()
    raw_data = b""
    start_time = time.time()
    while time.time() - start_time < 3:
        if ser.in_waiting > 0:
            byte = ser.read(1)
            raw_data += byte
            if byte == b'\n':
                break
        else:
            time.sleep(0.1)
    
    if raw_data:
        if raw_data.count(b'\x00') > len(raw_data) * 0.8:
            print("[ERROR] Received mostly NULL bytes! Resetting serial connection...")
            return None
        try:
            decoded_data = raw_data.decode('utf-8', errors='ignore').strip()
            valid_data = re.sub(r'[^0-9.,-]', '', decoded_data)
            return valid_data
        except UnicodeDecodeError:
            print(f"[WARNING] Received non-decodable data: {repr(raw_data)}")
            return ""
    return ""

def main():
    global message_counter
    print("[DEBUG] Starting main function...")
    client, mqtt_topic = setup_mqtt()
    client.loop_start()
    last_message_time = time.time()
    
    try:
        while True:
            ser = setup_serial()
            raw_data = read_serial_data(ser)
            if raw_data is None or time.time() - last_message_time > 30:
                ser.close()
                time.sleep(2)
                continue
            if not raw_data:
                ser.close()
                time.sleep(2)
                continue
            
            parts = raw_data.split(',')
            if len(parts) != 2:
                ser.close()
                time.sleep(2)
                continue
            try:
                temp = float(parts[0])
                hum = float(parts[1])
            except ValueError:
                ser.close()
                time.sleep(2)
                continue
            
            last_message_time = time.time()
            sensor_data = {"temperature": temp, "humidity": hum}
            client.publish(mqtt_topic, json.dumps(sensor_data), qos=0, retain=True)
            message_counter += 1
            print(f"[INFO] [Message Count: {message_counter}] Successfully Published to MQTT: {sensor_data}")
    except KeyboardInterrupt:
        print("[DEBUG] KeyboardInterrupt detected, stopping script...")
    finally:
        client.loop_stop()
        client.disconnect()
        print("[INFO] Resources cleaned up. Exiting.")

if __name__ == "__main__":
    main()
