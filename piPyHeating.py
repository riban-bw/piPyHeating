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
button = Button(27, True, None, 0.05, 0)
led = PWMLED(22, False)
state = 0
roomTemp = 0
currentTemp = {roomSensor: 0}
roomSetTemp = 21.5
cylinderSetTemp = 55

# Dictionary contains scheduled events (on, off, bitwise days - Monday = 1, Sunday = 64)
schedule = {
	"timer1": { "on": 360, "off": 600, "days": 127},
	"timer2": {"on": 900, "off": 1350, "days": 127},
}

# Get raw temeperature sensor value
def getRawTemp(sensor):
	tempSensor = '/sys/bus/w1/devices/' + sensor + '/w1_slave'
	try:
		f = open(tempSensor, 'r')
		lines = f.readlines()
		f.close()
		return lines
	except:
		print("Sensor " + sensor + " error")

# Get temperature sensor value in degrees Celsius
def getTemp(sensor):
	lines = getRawTemp(sensor)
	while lines[0].strip()[-3:] != 'YES':
		time.sleep(0.2)
		lines = getRawTemp(sensor)

	temp_output = lines[1].find('t=')

	if temp_output != -1:
		temp_string = lines[1].strip()[temp_output+2:]
		temp_c = float(temp_string) / 1000.0
		if temp_c != 85:
			currentTemp[sensor] = temp_c

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
		if currentTemp[roomSensor] > roomSetTemp:
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
	print now.time(), state, currentTemp[roomSensor]
	return 60 - now.time().second

# Handle alarm signal (triggered on minute boundary)
def onAlarm(signum, frame):
	getTemp(roomSensor)
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


