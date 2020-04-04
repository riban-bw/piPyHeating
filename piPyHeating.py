# riban piPyHeating.py
# (c) riban 2020
# Provides timer control of heating pump and boiler

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
import json
from uuid import uuid4
import sys 
from w1thermsensor import W1ThermSensor as w1bus
import git

button = Button(3, True, None, 0.05, 0)
led = PWMLED(22, False)
state = 0
stateName = {0: "Off", 1: "On"}
WebSocketConnections = set()

# Dictionary of DS18S20 temperature sensors
sensors = {}
ds_sensors = {}

# Dictionary contains scheduled events (on, off, bitwise days - Monday = 1, Sunday = 64)
schedule = {}

version = "Unversioned"

# Activate timer if within a timer window
def TimerActive():
	global state
	now = datetime.now()
	minutesSinceMidnight = now.time().hour * 60 + now.time().minute
	dayMask = 1 << now.date().weekday()
	state = 0
	for entry in schedule:
		event = schedule[entry]
		if dayMask & event["days"] and minutesSinceMidnight >= event["on"] and minutesSinceMidnight < event["off"]:
			state = 1

# Create a web handler
def make_app():
	settings = {"template_path": "templates", "static_path": "static_files"}
	return tornado.web.Application([
		(r'/$', HomeHandler),
		(r'/timers$', TimersHandler),
		(r'/sensors$', SensorsHandler),
		(r'/getstate$', GetStateHandler),
		(r'/websocket$', OnWebsocket),
		(r'/about$', OnAbout)
	], **settings, debug=True)

# Handle web home page request
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
				incrementRoom(0.1)
				updateWebsockets()
			elif action == 'down':
				incrementRoom(-0.1)
				updateWebsockets()
			self.redirect('/')    # Redirect back to the root url
			return
		super().render("home.html", title="riban Heating", sensors=sensors, state=stateName[state])

# Handle web timer page request
class TimersHandler(tornado.web.RequestHandler):
	def get(self):
		action = self.get_argument('action', None)
		if action != None:
			if action == 'delete':
				try:
					del schedule[self.get_argument('timer', None)]
					writeConfig()
				except:
					print("Could not delete timer")
			if action == 'new':
				timer  = str(uuid4())
				while timer in schedule:
					timer = str(uuid4())
				schedule[timer] = {"on": 420, "off": 1350, "days": 127}
				writeConfig()
			self.redirect('/timers')
			return
		super().render("timers.html", title="riban Heating", timers=schedule)

# Handle web sensor page request
class SensorsHandler(tornado.web.RequestHandler):
	def get(self):
		action = self.get_argument('action', None)
		if action != None:
			if action == 'delete':
				try:
					del sensors[self.get_argument('sensor', None)]
					writeConfig()
				except:
					print("Could not delete sensor")
			self.redirect('/timers')
			return
		super().render("sensors.html", title="riban Heating", sensors=sensors)

# Handle web getstate requests
class GetStateHandler(tornado.web.RequestHandler):
	def get(self):
		super().render("getstate.html", title="riban Heating", state=stateName[state])

# Handle web about requests
class OnAbout(tornado.web.RequestHandler):
	def get(self):
		super().render("about.html", title="riban Heating", version=version)

# Handle websocket request
class OnWebsocket(tornado.websocket.WebSocketHandler):
	global WebSocketConnections
	def open(self):
		WebSocketConnections.add(self)
		print("Added websocket")
	def on_message(self, message):
		print("Websocket message recieved", message)
		try:
			data = json.loads(message)
			if 'updatetimer' in data:
				thisUpdate = data['updatetimer']
				if thisUpdate['timer'] in schedule:
					if thisUpdate['param'] == 'on':
						pt = datetime.strptime(thisUpdate['value'], '%H:%M')
						schedule[thisUpdate['timer']]['on'] = pt.minute + pt.hour * 60
					if thisUpdate['param'] == 'off':
						pt = datetime.strptime(thisUpdate['value'], '%H:%M')
						schedule[thisUpdate['timer']]['off'] = pt.minute + pt.hour * 60
					if thisUpdate['param'].split(':')[0] == 'day':
						index = int(thisUpdate['param'].split(':')[1])
						mask  = 1 << index
						if(thisUpdate['value'] == 'true'):
							schedule[thisUpdate['timer']]['days'] = schedule[thisUpdate['timer']]['days'] | mask
						else:
							schedule[thisUpdate['timer']]['days'] = schedule[thisUpdate['timer']]['days'] & ~mask
			if 'updatesensor' in data:
				thisUpdate = data['updatesensor']
				if thisUpdate['param'] == 'setpoint':
					sensors[thisUpdate['sensor']]['setpoint'] = float(thisUpdate['value'])
					updateWebsockets()
			writeConfig()
		except:
			print("Error parsing websocket message", sys.exc_info()[0])
		
	def on_close(self):
		WebSocketConnections.remove(self)
		print("Removed websocket")

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
	sensors["room"]["setpoint"] += value
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
		if sensors["room"]["value"] < sensors["room"]["setpoint"]:
			pumpOn = 1
			boilerOn = 1
		if sensors["cylinder"]["value"] < sensors["cylinder"]["setpoint"]:
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
	
	print(now.strftime("%H:%M:%S %d/%m/%Y  [") + stateName[state] + "] Room: ", format(sensors["room"]["value"],'.2f'), " Water ",  format(sensors["cylinder"]["value"],'.2f'))
	return 60 - now.time().second

# Send update to websocket clients
def updateWebsockets():
	message = {"state": state,
				"temproom": format(sensors['room']['value'], '.2f'),
				"setpointroom": format(sensors['room']['setpoint'],'.1f'),
				"tempcylinder": format(sensors['cylinder']['value'],'.2f'),
				"setpointcylinder": format(sensors['cylinder']['setpoint'],'.1f')}
	[client.write_message(message) for client in WebSocketConnections ]


# Handle alarm signal (triggered on minute boundary)
def onAlarm(signum, frame):
	for sensor in sensors:
		try:
			sensors[sensor]['value'] = ds_sensors[sensor].get_temperature()
		except:
			print('Failed to get temperature from sensor', sensor, sys.exc_info()[0])
	alarm(processTemp())

# Read configuration from file
def readConfig():
	print("Reading config...")
	global sensors
	global schedule
	global ds_sensors
	with open('config.json') as config:
		try:
			data = json.load(config)
			sensors = data['sensors']
			schedule = data['timers']
			for sensor in sensors:
				ds_sensors[sensor] = w1bus(w1bus.THERM_SENSOR_DS18B20, sensors[sensor]['id'])
		except:
			print("ERROR: Cannot read or parse JSON configuration")

# Write configuration to file
def writeConfig():
	global sensors
	global schedule
	data = json.dumps({"timers": schedule, "sensors": sensors}, indent=4)
	with open('config.json', 'w') as config:
		config.write(data)

# Main loop - just wait for a signal
if __name__ == "__main__":
	try:
		repo = git.Repo(search_parent_directories=True)
		version = repo.head.object.hexsha
	except:
		version = "Unversioned"

	app = make_app()
	app.listen(8000)

	# Register for button events
	button.when_pressed = onButton

	# Configure alarm signal handler
	signal.signal(signal.SIGALRM, onAlarm)
	
	# Read timers from json file
	readConfig()
	
	# Set defaults if sensors not correctly populated, e.g. bad json content
	try:
		print("Room sensor id: ", sensors["room"]["id"])
	except:
		sensors["room"] = {"id": "28-0000053f0ba3", "name": "Hall", "setpoint": 21.3, "value": 80.0}
	try:
		print("Water sensor id: ", sensors["cylinder"]["id"])
	except:
		sensors["cylinder"] = {"id": "28-000005a2a817", "name": "Water", "setpoint": 43.0, "value": 80.0}
	# Set defaults if timers not correctly populated, e.g. bad json content
	try:
		for timer in schedule:
			print(timer, ":", schedule[timer]['on'], "-", schedule[timer]['off'], schedule[timer]['days'])
	except:
		schedule = {str(uuid4): { "on": 400, "off": 1350, "days": 127}}


	# Turn on heating if timer is active
	TimerActive()

	# Trigger alarm at startup
	alarm(1)

	tornado.ioloop.IOLoop.current().start()
