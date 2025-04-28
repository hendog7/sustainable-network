import face_recognition 
from picamera2 import Picamera2 
import numpy as np 
import smtplib 
from email.message import EmailMessage 
from gpiozero import MotionSensor 
from signal import pause 
from time import sleep 
import cv2 
import socket

# Get a reference to the Raspberry Pi camera and motion sensor
camera = Picamera2() 
camera.configure(camera.create_still_configuration()) 
camera.resolution = (640, 480)  # Lower resolution to speed up image capture 
pir = MotionSensor(17, pull_up=False) 


# Email credentials 
from_email_addr = "bristolgroupproject@gmail.com" 
from_email_pass = "uzqu onkf ddvj emys" 


# SMTP Server setup 
server = smtplib.SMTP('smtp.gmail.com', 587) 
server.starttls() 
server.login(from_email_addr, from_email_pass) 

# SOCKET server setup
#socket_server = socket.socket()


# Admin email for security alerts 
admin_email = "ij22387@bristol.ac.uk" 


# List of people to recognize (name, image, and email) 
people = [ 
    {"name": "Henna Parmar", "image_path": "henna.jpg", "email_address": "ij22387@bristol.ac.uk"}, 
    {"name": "Jennie Cohen", "image_path": "jennie.jpg", "email_address": "pl22413@bristol.ac.uk"}, 
    {"name": "Steven Badrie", "image_path": "steven.jpg", "email_address": "ma22790@bristol.ac.uk"}, 
    {"name": "Samuel Ogunmwonyi", "image_path": "sam.jpg", "email_address": "my22652@bristol.ac.uk"}, 
    {"name": "Haoran Shi", "image_path": "haoran.jpg", "email_address": "or21100@bristol.ac.uk"} 
] 


# Initialize lists to store known face encodings and names 
known_face_encodings = [] 
known_face_names = [] 
known_face_emails = [] 


# Load each person's image and encode their face 
print("Loading known face images...") 
for person in people: 
    image = face_recognition.load_image_file(person["image_path"]) 
    face_encoding = face_recognition.face_encodings(image)[0] 
    known_face_encodings.append(face_encoding) 
    known_face_names.append(person["name"]) 
    known_face_emails.append(person["email_address"]) 
print("face images loaded") 

  
frame_counter = 0 


def faceDetect(): 
    print("Capturing image...") 
    frame = camera.capture_array() 
    face_locations = face_recognition.face_locations(frame, model="hog")         
    print("Found {} faces in image.".format(len(face_locations))) 
    face_encodings = face_recognition.face_encodings(frame, face_locations) 

    # Loop over each detected face 

    for face_encoding, face_location in zip(face_encodings, face_locations): 
        match = face_recognition.compare_faces(known_face_encodings, face_encoding) 
        name = "<Unknown Person>" 
        email = None 

        if True in match: 
            first_match_index = match.index(True) 
            name = known_face_names[first_match_index] 
            email = known_face_emails[first_match_index] 

        print("I see someone named {}!".format(name)) 

        if email: 
            msg = EmailMessage() 
            msg['From'] = from_email_addr 
            msg['To'] = email 
            msg['Subject'] = 'Welcome Home!' 
            msg.set_content("Welcome home, {}! The temperature is: and the humidity is: ".format(name)) 
            server.send_message(msg) 
            print('Email sent to', email) 

        else: 
            # Save image of unknown person 
            image_path = "unknown_face.jpg" 
            cv2.imwrite(image_path, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)) 
             
            # Send security alert email 
            msg = EmailMessage() 
            msg['From'] = from_email_addr 
            msg['To'] = admin_email 
            msg['Subject'] = 'Security Alert: Unknown Person Detected!' 
            msg.set_content("An unknown person was detected. See the attached image.") 

             
            with open(image_path, 'rb') as img_file: 
                msg.add_attachment(img_file.read(), maintype='image', subtype='jpeg', filename='unknown_face.jpg') 
        
            server.send_message(msg) 
            print('Security alert email sent to admin.') 

 
while True:  

    pir.wait_for_motion() 
    print("motion detected") 
    camera.start() 
    faceDetect() 
    pir.wait_for_no_motion() 
    camera.stop() 
