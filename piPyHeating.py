# riban piPyHeating.py
# (c) riban 2020
# Provides timer control of heating pump and boiler

import os
import time
from gpiozero import Button
from gpiozero import PWMLED
from gpiozero import LED
from signal import pause
from signal import alarm
import signal
from datetime import datetime
import tornado.web
import tornado.ioloop
import tornado.websocket

os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')

button = Button(3, True, None, 0.05, 0)
led = PWMLED(22, False)
state = 0
stateName = {0: "Off", 1: "On"}
WebSocketConnections = set()

# Dictionary of DS18S20 temperature sensors
sensors = {
	"room": {"id": "28-0000053f0ba3", "name": "Hall", "setPoint": 213, "value": 800},
	"cylinder": {"id": "28-000005a2a817", "name": "Water", "setPoint": 430, "value": 800}
}

# Dictionary contains scheduled events (on, off, bitwise days - Monday = 1, Sunday = 64)
schedule = {
	"timer1": { "on": 360, "off": 600, "days": 63},
	"timer2": {"on": 900, "off": 1350, "days": 127},
	"timer3": { "on": 420, "off": 720, "days": 64},
}

# Create a web handler
def make_app():
	settings = {"template_path": "templates"}
	return tornado.web.Application([
		(r'/$', HomeHandler),
		(r'/getstate$', GetStateHandler),
		(r'/websocket$', OnWebsocket)
	], **settings)

# Handle web home page requests
class HomeHandler(tornado.web.RequestHandler):
	def get(self):
		action = self.get_argument('action', None)
		if action != None:
			if action == 'on':
				turnOn()
				updateWebsockets()
			elif action == 'off':
				turnOff()
				updateWebsockets()
			elif action == 'up':
				incrementRoom(1)
				updateWebsockets()
			elif action == 'down':
				incrementRoom(-1)
				updateWebsockets()
			self.redirect('/')    # Redirect back to the root url
			return
		super().render("home.html", title="riban Heating", sensors=sensors, state=stateName[state])

# Handle web getstate requests
class GetStateHandler(tornado.web.RequestHandler):
	def get(self):
		super().render("getstate.html", title="riban Heating", state=stateName[state])


# Handle websocket request
class OnWebsocket(tornado.websocket.WebSocketHandler):
	global WebSocketConnections
	def open(self):
		WebSocketConnections.add(self)
		print("Added websocket")
	def on_message(self, message):
		print("Websocket message recieved")
	def on_close(self):
		WebSocketConnections.remove(self)
		print("Removed websocket")

# Get raw temeperature sensor value from sensor name (room / cylinder)
def getRawTemp(sensor):
	tempSensor = '/sys/bus/w1/devices/' + sensors[sensor]["id"] + '/w1_slave'
	try:
		f = open(tempSensor, 'r')
		lines = f.readlines()
		f.close()
		return lines
	except:
		print("Sensor " + sensors[sensor]["name"] + " error")

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
		temp_c = int(temp_string) / 100
		if temp_c != 850:
			sensors[sensor]["value"] = temp_c

# Handle button event
def onButton():
	global state
	if state == 0:
		state = 1
		led.on()
	else:
		state = 0
		led.off()
	alarm(1)

def turnOn():
	global state
	state = 1
	processTemp()

def turnOff():
	global state
	state = 0
	processTemp()

def incrementRoom(value):
	sensors["room"]["setPoint"] += value
	processTemp()

# Read temperature sensors and activate outputs
# Returns seconds until next minute boundary
def processTemp():
	global pump
	global boiler
	global state
	now = datetime.now()
	minutesSinceMidnight = now.time().hour * 60 + now.time().minute
	dayMask = 1 << now.date().weekday()
	for entry in schedule:
		event = schedule[entry]
		if dayMask & event["days"] and minutesSinceMidnight == event["on"]:
			state = 1
		if dayMask & event["days"] and minutesSinceMidnight == event["off"]:
			state = 0
	if state == 0:
		try:
			pump.close()
			boiler.close()
		except:
			pass
		led.off()
	if state == 1:
		pumpOn = 0
		boilerOn = 0
		if sensors["room"]["value"] < sensors["room"]["setPoint"]:
			pumpOn = 1
			boilerOn = 1
		if sensors["cylinder"]["value"] < sensors["cylinder"]["setPoint"]:
			boilerOn = 1
		
		try:
			if pumpOn:
				pump = LED(18)
			else:
				pump.close()
		except:
			pass

		try:
			if boilerOn:
				boiler = LED(17)
			else:
				boiler.close()
		except:
			pass

		if boilerOn and pumpOn:
			led.blink()
		elif boilerOn:
			led.pulse()
		else:
			led.on()
	
	updateWebsockets()
	
	print(now.strftime("%H:%M:%S %d/%m/%Y  [") + stateName[state] + "] Room: ", round(float(sensors["room"]["value"])/10,2), " Water ",  round(float(sensors["cylinder"]["value"])/10,2))
	return 60 - now.time().second

# Send update to websocket clients
def updateWebsockets():
	print("Updating websockets")
	message = {"temp": str(round(float(sensors["room"]["value"])/10,2)), "state": state, "setpoint": str(round(float(sensors["room"]["setPoint"])/10,2))}
	[client.write_message(message) for client in WebSocketConnections ]


# Handle alarm signal (triggered on minute boundary)
def onAlarm(signum, frame):
	getTemp("room")
	getTemp("cylinder")
	alarm(processTemp())

# Main loop - just wait for a signal
if __name__ == "__main__":
	app = make_app()
	app.listen(8000)

	# Register for button events
	button.when_pressed = onButton

	# Configure alarm signal handler
	signal.signal(signal.SIGALRM, onAlarm)


	# Trigger alarm at startup
	alarm(1)

	tornado.ioloop.IOLoop.current().start()
