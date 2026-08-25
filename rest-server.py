import subprocess
import time
import datetime
from subprocess import PIPE
from gpiozero import CPUTemperature

fan_status = 1

def turn_fan_off():
    print("TURNING FAN OFF", datetime.datetime.now().time())
    process = subprocess.Popen(['uhubctl','-l', '1-1', '-p' , '2', '-a', '0'], stdout=PIPE, bufsize=-1)

def turn_fan_on():
    print("TURNING FAN ON", datetime.datetime.now().time())
    process = subprocess.Popen(['uhubctl','-l', '1-1', '-p' , '2', '-a', '1'], stdout=PIPE, bufsize=-1)

def checkTemp():
    global fan_status
    temp = CPUTemperature().temperature
    print(temp)
    if temp > 55:
        if fan_status == 0:
            print("Run fan")
            fan_status = 1
            turn_fan_on()
    elif temp < 48:
        if fan_status == 1:
            print("Turn off fan")
            fan_status = 0
            turn_fan_off()

def is_night_time():
    now = datetime.datetime.now().time()
    start_night_time = datetime.time(22, 0)
    end_night_time = datetime.time(8, 0)
    return now >= start_night_time or now < end_night_time

def run_chron():
    if is_night_time():
      print("NIGHTY NIGHTY")
      return
    
    turn_fan_on()
    time.sleep(300)
    turn_fan_off()

run_chron()
