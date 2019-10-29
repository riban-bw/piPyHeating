import os
import time
from gpiozero import Button
from gpiozero import PWMLED
from gpiozero import LED
from signal import pause
from signal import alarm
import signal
from datetime import datetime

os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')

roomSensor = '28-0000053f0ba3'
cylinderSensor = '28-000005a2a817'
button = Button(27, True, None, 0.05, 0)
led = PWMLED(22, False)
state = 0
roomTemp = 0
currentTemp = {roomSensor: 0}
roomSetTemp = 21.5
cylinderSetTemp = 55

# Dictionary of DSB18S20 temperature sensors
sensors = {
	"room": {"id": "28-0000053f0ba3", "name": "Hall",  "value": 0},
	"cylinder": {"id": "28-000005a2a817", "name": "Water", "value": 0}
}

# Dictionary contains scheduled events (on, off, bitwise days - Monday = 1, Sunday = 64)
schedule = {
	"timer1": { "on": 360, "off": 600, "days": 127},
	"timer2": {"on": 900, "off": 1350, "days": 127},
}

# Get raw temeperature sensor value from sensor name (room / cylinder)
def getRawTemp(sensor):
	tempSensor = '/sys/bus/w1/devices/' + sensors[sensor]["id"] + '/w1_slave'
	try:
		f = open(tempSensor, 'r')
		lines = f.readlines()
		f.close()
		return lines
	except:
		print("Sensor " + sensors[sensor][name] + " error")

# Get temperature sensor value in degrees Celsius
def getTemp(sensor):
	lines = getRawTemp(sensor)
	if lines == None:
		return
	while lines[0].strip()[-3:] != 'YES':
		time.sleep(0.2)
		lines = getRawTemp(sensor)

	temp_output = lines[1].find('t=')

	if temp_output != -1:
		temp_string = lines[1].strip()[temp_output+2:]
		temp_c = round(float(temp_string) / 1000.0, 1)
		if temp_c != 85:
			sensors[sensor]["value"] = temp_c

# Handle button event
def onButton():
	global state
	if state == 0:
		state = 1
	else:
		state = 0
	processTemp()

# Read temperature sensors and activate outputs
def processTemp():
	global pump
	global boiler
	global state
	now = datetime.now()
	dayMask = 1 << now.date().weekday()
	for entry in schedule:
		event = schedule[entry]
		if dayMask | event["days"] and now.time().minute == event["on"]:
			state = 1
		if dayMask | event["days"] and now.time().minute == event["off"]:
			state = 0
	if state == 0:
		try:
			pump.close()
			boiler.close()
		except:
			pass
		led.off()
	if state == 1:
		if sensors["room"]["value"] > roomSetTemp:
			try:
				pump.close()
				boiler.close()
			except:
				pass
			led.on()
		else:
			try:
				pump = LED(18)
				boiler = LED(17)
			except:
				pass
			led.blink()
	print now.strftime("%H:%M:%S %d/%m/%Y"), state, sensors["room"]["value"]
	return 60 - now.time().second

# Handle alarm signal (triggered on minute boundary)
def onAlarm(signum, frame):
	getTemp("room")
	alarm(processTemp())

# Register for button events
button.when_pressed = onButton

# Configure alarm signal handler
signal.signal(signal.SIGALRM, onAlarm)

# Trigger alarm at startup
alarm(1)

# Main loop - just wait for a signal
while True:
	pause()


