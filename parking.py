import base64
import hashlib
import hmac
import platform
import sys
import os
import threading
import time
import requests
import yaml
import socketio

IS_RASPBERRY = (platform.machine().startswith("arm") or platform.machine().startswith("aarch")) and ("raspberrypi" in os.uname().nodename or "rpi6" in os.uname().nodename)
DEFAULT_HOST = "hackeps.ddns.net/backend"
DEFAULT_HTTPS = True

if IS_RASPBERRY:
    import RPi.GPIO as GPIO #pip install python3-rpi.gpio
else:
    import keyboard  #pip install keyboard

def generate_hmac_signature(client_id, secret_key:str, timestamp, data):
    message = f"{client_id}{timestamp}{data}"
    signature = hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).digest()
    signature_base64 = base64.b64encode(signature).decode()
    return signature_base64

def generate_auth_header(client_id, secret_key, data):
    timestamp = int(time.time())
    signature = generate_hmac_signature(client_id, secret_key, timestamp, data)
    return f"hmac {client_id}:{signature}:{timestamp}"

class ParkingSocket:
    
    def __init__(self, parkingId:str, secret, host=DEFAULT_HOST, httpsMode=DEFAULT_HOST, retry_timeout=10):
        self.sio = socketio.Client()
        self.parkingId = parkingId
        self.secret = secret
        self.host = f"ws{'s' if httpsMode else ''}://{host}/socket"
        self.register_events()
        self.retry_timeout = retry_timeout
        self.running = True
        
    def register_events(self):

        @self.sio.on('connect', namespace='/socket')
        def connect():
            print("Conexión establecida con el servidor en /socket")
            self.sio.emit("status_parking", {"status": "online", "Authorization": generate_auth_header(self.parkingId, self.secret, "status_parking")}, namespace="/socket")

        @self.sio.on('disconnect', namespace='/socket')
        def disconnect():
            print("Desconectado del servidor")
            self.sio.emit("status_parking", {"status": "offline", "parkingId": self.parkingId, "Authorization": generate_auth_header(self.parkingId, self.secret, "status_parking")}, namespace="/socket")

        @self.sio.on('connect_error', namespace='/socket')
        def connect_error(data):
            print("Error al conectar:", data)
            
        @self.sio.on('error', namespace='/socket')
        def error(data):
            print("Error:", data)

    def connect(self):
        while self.running:
            try:
                print("Intentando conectar a", self.host)
                self.sio.connect(self.host, transports=["websocket"])
                self.sio.wait()
            except Exception as e:
                print("Error al intentar conectar:", str(e))
                
            if not self.running:
                break
                
            print("Intentando reconectar en", self.retry_timeout, "segundos")
            time.sleep(self.retry_timeout)
            
        self.sio.disconnect()
        print("Cliente Socket.IO detenido")
            
    def stop(self):
        self.running = False
            
    def emitChange(self, occupation):
        self.sio.emit("change_parking", {"parkingId": self.parkingId, "occupation": occupation, "Authorization": generate_auth_header(self.parkingId, self.secret, "change_parking")}, namespace="/socket")

class Parking:
    
    def __init__(self, confPath="conf.yaml", BEAM_IN_PIN=17, BEAM_OUT_PIN=27, SIMULATED_IN_KEY="space", SIMULATED_OUT_KEY="enter", retry_timeout=10):
        self.confPath = confPath
        self.conf = {}
        
        self.BEAM_IN_PIN = BEAM_IN_PIN
        self.BEAM_OUT_PIN = BEAM_OUT_PIN
        self.SIMULATED_IN_KEY = SIMULATED_IN_KEY
        self.SIMULATED_OUT_KEY = SIMULATED_OUT_KEY
        self.retry_timeout = retry_timeout
        self.beam_status = False
        
        self.readConf()
        
        self.parking = self.getParking()
        self.conf["size"] = self.parking.get("size")
        
        self.writeConf()
        
        self.socket = ParkingSocket(self.conf.get('parkingId'), self.conf.get('secret'), self.conf.get("host", DEFAULT_HOST), self.conf.get("https", DEFAULT_HTTPS), retry_timeout=retry_timeout)
                  
        threading.Thread(target=self.socket.connect).start()
                        
    def readConf(self):
        
        with open(self.confPath, "r") as f:
            self.conf = yaml.safe_load(f)
            self.conf["occupation"] = self.conf.get("occupation") or 0
            
    def writeConf(self):
        
        with open(self.confPath, "w") as f:
            yaml.dump(self.conf, f)
            
    def getParking(self):
        parkingId = self.conf.get("parkingId")
        host = self.conf.get("host", DEFAULT_HOST)
        
        httpsMode = self.conf.get("https", DEFAULT_HTTPS)
        
        url = f"http{'s' if httpsMode else ''}://{host}/api/v1/parking/{parkingId}"
                  
        while True:
                
            try:
                
                response = requests.get(url)
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Error getting parking data: {response.status_code}:\n{response.text}")
                    
            except KeyboardInterrupt:
                print("\nExiting program.")
                sys.exit(0)
                
            except Exception as e:
                print(f"Error getting parking data: {str(e)}")
                
            print(f"Trying again in {self.retry_timeout} seconds")
            time.sleep(self.retry_timeout)
        
    def beam_broken(self):
        
        if IS_RASPBERRY:
            input = GPIO.input(self.BEAM_IN_PIN) == 0
            output = GPIO.input(self.BEAM_OUT_PIN) == 0        
        else:
            input = keyboard.is_pressed(self.SIMULATED_IN_KEY)
            output = keyboard.is_pressed(self.SIMULATED_OUT_KEY)
        
        return input or output, input

    def break_beam_callback(self):
        
        _beam_status, enterMode = self.beam_broken()
        
        if _beam_status != self.beam_status:
            if _beam_status:
                
                print("Beam broken")
                
                occupation = self.conf.get("occupation")
                occupation += 1 if enterMode else -1
                if occupation < 0: occupation = 0
                elif occupation > self.conf.get("size"): occupation = self.conf.get("size")
                
                self.conf["occupation"] = occupation
                
                self.writeConf()
                
                print(f"Occupation: {occupation}/{self.conf.get('size')}")
                self.socket.emitChange(occupation)
                
            else:
                print("Beam unbroken")
        
        self.beam_status = _beam_status
        
    def start(self):
        
        try:
                
            if IS_RASPBERRY:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.BEAM_IN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.setup(self.BEAM_OUT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

                GPIO.add_event_detect(self.BEAM_IN_PIN, GPIO.BOTH, callback=lambda x: self.break_beam_callback())
                GPIO.add_event_detect(self.BEAM_OUT_PIN, GPIO.BOTH, callback=lambda x: self.break_beam_callback())
                print("Running on Raspberry Pi. Press Ctrl+C to exit.")
            else:
                print(f"Running on PC. Press '{self.SIMULATED_IN_KEY}' to simulate sensor break in. Press '{self.SIMULATED_OUT_KEY}' to simulate sensor break out. Press Ctrl+C to exit.")

            # Bucle principal
            while True:
                if not IS_RASPBERRY:
                    self.break_beam_callback()
                pass

        except KeyboardInterrupt:
            print("\nExiting program.")

        finally:
            if IS_RASPBERRY:
                GPIO.cleanup()
            else:
                print("Program ended.")
                
            self.socket.stop()
                
parking = Parking()
parking.start()
