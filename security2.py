from picamera2 import Picamera2
from email.message import EmailMessage 
from gpiozero import MotionSensor 
import face_recognition 
import numpy as np 
import smtplib 
import cv2
import json
import paho.mqtt.client as mqtt
import time

class Security:
    def __init__(self, email_address: str, email_pwd: str, resolution=(640, 480), pin=17):
        self._camera = self.__init_camera(resolution)
        self._pir = self.__init_motion_sensor(pin)
        self._server = self.__init_email_server(email_address, email_pwd)
        self.temp = None  # Store latest temperature
        self.hum = None   # Store latest humidity

        # Setup MQTT to receive temperature & humidity updates
        self.__setup_mqtt()

    def __init_camera(self, resolution):
        """Initialize and configure the camera."""
        camera = Picamera2()
        camera.configure(camera.create_still_configuration())
        camera.resolution = resolution
        return camera

    def __init_motion_sensor(self, pin):
        """Initialize the motion sensor."""
        return MotionSensor(pin, pull_up=False)

    def __init_email_server(self, email_address, email_pwd):
        """Setup SMTP email server and load known faces."""
        self.__from_email_addr = email_address
        self.__from_email_pass = email_pwd
        self.__admin_email = "ij22387@bristol.ac.uk"  # Change to your admin email

        # Setup SMTP Server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(email_address, email_pwd)

        # Load registered people
        with open('Registered People.json') as f:
            data = json.load(f)
            people = data["people"]

        self.__known_face_encodings = []
        self.__known_face_names = []
        self.__known_face_emails = []

        print("Loading known face images...")
        for person in people:
            image = face_recognition.load_image_file(person["image_path"])
            face_encoding = face_recognition.face_encodings(image)[0]
            self.__known_face_encodings.append(face_encoding)
            self.__known_face_names.append(person["name"])
            self.__known_face_emails.append(person["email_address"])
        print("Face images loaded.")

        return server

    def __setup_mqtt(self):
        """Setup MQTT client to receive temperature and humidity updates from a JSON config file."""
        try:
            with open("MQTT-config.json", "r") as f:
                mqtt_config = json.load(f)
            
            # Ensure all required keys exist
            if not all(k in mqtt_config for k in ["MQTT_BROKER", "MQTT_PORT", "MQTT_TOPIC"]):
                raise KeyError("Missing MQTT_BROKER, MQTT_PORT, or MQTT_TOPIC in MQTT-config.json")

            mqtt_broker = mqtt_config["MQTT_BROKER"]
            mqtt_port = int(mqtt_config["MQTT_PORT"])  # Ensure it's an integer
            mqtt_topic = mqtt_config["MQTT_TOPIC"]

            self.mqtt_client = mqtt.Client()
            self.mqtt_client.on_message = self._on_mqtt_message
            self.mqtt_client.connect(mqtt_broker, mqtt_port, 60)
            self.mqtt_client.subscribe(mqtt_topic)
            self.mqtt_client.loop_start()  # Run MQTT in background

            print(f"[Security] Connected to MQTT broker {mqtt_broker}:{mqtt_port}, subscribed to {mqtt_topic}")

        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            print(f"[Security] Error loading MQTT config: {e}")
            self.mqtt_client = None


    def _on_mqtt_message(self, client, userdata, msg):
        """Handle incoming MQTT messages and update temp/humidity."""
        try:
            data = json.loads(msg.payload.decode())
            self.temp = data.get("temperature", 0.0)
            self.hum = data.get("humidity", 0.0)
            #print(f"[Security] Updated Temp: {self.temp}°C, Humidity: {self.hum}%")
        except json.JSONDecodeError:
            print("[Security] Invalid MQTT message received")

    def _faceDetect(self):
        """Capture an image, detect faces, and send appropriate email alerts."""
        print("Capturing image...")
        frame = self._camera.capture_array()
        face_locations = face_recognition.face_locations(frame, model="hog")
        print(f"Found {len(face_locations)} faces in image.")
        face_encodings = face_recognition.face_encodings(frame, face_locations)

        for face_encoding in face_encodings:
            match = face_recognition.compare_faces(self.__known_face_encodings, face_encoding)
            name = "<Unknown Person>"
            email = None

            if True in match:
                first_match_index = match.index(True)
                name = self.__known_face_names[first_match_index]
                email = self.__known_face_emails[first_match_index]

            print(f"I see someone named {name}!")

            if email:
                msg = EmailMessage()
                msg['From'] = self.__from_email_addr
                msg['To'] = email
                msg['Subject'] = 'Welcome Home!'
                msg.set_content(f"Welcome home, {name}! The temperature is: {self.temp}°C and the humidity is: {self.hum}%.")
                self._server.send_message(msg)
                print(f'Email sent to {email}')
            else:
                # Save image of unknown person
                image_path = "unknown_face.jpg"
                cv2.imwrite(image_path, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

                # Send security alert email
                msg = EmailMessage()
                msg['From'] = self.__from_email_addr
                msg['To'] = self.__admin_email
                msg['Subject'] = 'Security Alert: Unknown Person Detected!'
                msg.set_content("An unknown person was detected. See the attached image.")

                with open(image_path, 'rb') as img_file:
                    msg.add_attachment(img_file.read(), maintype='image', subtype='jpeg', filename='unknown_face.jpg')

                self._server.send_message(msg)
                print('Security alert email sent to admin.')

    def run(self):
        """Main loop to monitor motion and trigger face detection."""
        while True:
            self._pir.wait_for_motion()
            print("Motion detected")
            self._camera.start()
            self._faceDetect()
            self._pir.wait_for_no_motion()
            self._camera.stop()


if __name__ == "__main__":
    sec = Security(email_address="bristolgroupproject@gmail.com", email_pwd="uzqu onkf ddvj emys")
    sec.run()
