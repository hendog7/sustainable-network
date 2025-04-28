import socket
import time
import re

HOST = "localhost"
PORT = 1024

message_counter = 0


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    global message_counter
    

    print(f"Server listening on {HOST}:{PORT}")
    conn, addr = server.accept()
    try:
        lastSentTime = time.time()
        while True:
            data = conn.recv(1024)
            #try:
            decoded = data.decode()
                #print("stop here")
            message_counter += 1
            print(f"Received:{decoded}, msg count: {message_counter}")
            #except UnicodeDecodeError:
            #    print("[WARNING] Decode error")
            #    decoded = None
            
            if time.time() - lastSentTime >= 20:
                #try:
                 #   parts = re.findall(r"[-+]?\d*\.\d+|\d+", decoded).split(',')
                #except UnicodeDecodeError:
                 #   print("[WARNING] Decode error")
                #temperature = parts[0]
                #humidity = part[1]
                
                #print(f"Welcome home! The temperature is: {temperature} and the humidity is: {humidity}")
                print(f"sent to email: {decoded}, msg count{message_counter}")
                lastSentTime = time.time()
            #countMessage += 1
            #sleep(0.1)
    except Exception as e:
            print(f"[ERROR] Failed to receive data")
    finally:
            conn.close()
            server.close()
            print("[DEBUG] Connection closed")

# Run main function
if __name__ == "__main__":
    print("[DEBUG] Running script as __main__")
    main()



