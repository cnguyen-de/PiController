from fastapi import FastAPI
import subprocess
from subprocess import PIPE

app = FastAPI()
fan_status = 1

@app.get("/")
def read_root():
    return {"Rest API for Raspberry Pi"}

@app.get("/fan/status")
def read_status():
    global fan_status
    return {"fan_status": fan_status}

@app.get("/fan/control/{status}")
def control_fan(status: int):
    global fan_status
    fan_status = status
    print(status)
    process = subprocess.Popen(['uhubctl','-l', '1-1', '-p' , '2', '-a', str(fan_status)], stdout=PIPE, bufsize=-1)
    return {"fan_status": fan_status}
