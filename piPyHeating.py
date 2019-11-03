import os
import time
from gpiozero import Button
from gpiozero import PWMLED
from gpiozero import LED
from signal import pause
from signal import alarm
import signal
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')

button = Button(27, True, None, 0.05, 0)
led = PWMLED(22, False)
state = 0
stateName = {0: "Off", 1: "On"}

# Dictionary of DSB18S20 temperature sensors
sensors = {
	"room": {"id": "28-0000053f0ba3", "name": "Hall", "setPoint": 213, "value": 800},
	"cylinder": {"id": "28-000005a2a817", "name": "Water", "setPoint": 430, "value": 800}
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
		temp_c = int(temp_string) / 100
		if temp_c != 850:
			sensors[sensor]["value"] = temp_c

# Handle button event
def onButton():
	global state
	if state == 0:
		state = 1
	else:
		state = 0
	processTemp()

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

	print(now.strftime("%H:%M:%S %d/%m/%Y  [") + stateName[state] + "] Room: ", round(float(sensors["room"]["value"])/10,2), " Water ",  round(float(sensors["cylinder"]["value"])/10,2))
	return 60 - now.time().second

# Handle alarm signal (triggered on minute boundary)
def onAlarm(signum, frame):
	getTemp("room")
	getTemp("cylinder")
	alarm(processTemp())

# Web server
host_name = 'rpi4.local'
host_port = 8000

class onHttp(BaseHTTPRequestHandler):
	def do_HEAD(self):
		self.send_response(200)
		self.send_header('Content-type', 'text/html')
		self.end_headers()

	def _redirect(self, path):
		self.send_response(303)
		self.send_header('Content-type', 'text/html')
		self.send_header('Location', path)
		self.end_headers()

	def do_GET(self):
		get_data = self.path.split("=")
		if len(get_data) > 1:
			if get_data[1] == 'on':
				turnOn()
			elif get_data[1] == 'off':
				turnOff()
			elif get_data[1] == 'up':
				incrementRoom(1)
			elif get_data[1] == 'down':
				incrementRoom(-1)
			self._redirect('/')    # Redirect back to the root url
			return
		html = '''
<html>
	<meta content='width=device-width, initial-scale=1' name='viewport'/>
	<head><style>
		.on {{
			height: 20%;
			font-size: 6vw;
			background-color: #339966;
			color: white;
			text-align: center;
			cursor: pointer;
			border-style: solid;
			display: table-cell;
			vertical-align: middle;
		}}
		.off {{
			height: 20%;
			font-size: 6vw;
			background-color: #333333;
			color: white;
			text-align: center;
			cursor: pointer;
			border-style: solid;
			display: table-cell;
			vertical-align: middle;
		}}
		.value {{
			height: 8%;
			font-size: 5vw;
			background-color: black;
			color: white;
			text-align: center;
			border-style: solid;
			display: table-cell;
			vertical-align: middle;
		}}
		.parent {{
			display: table;
			height: 100%;
			width: 100%;
		}}
		.row {{
			display: table-row;
		}}

	</style></head>
	<body>
		<div class="parent">
			<div class="row"><div class = "value">Current: {}&deg;</div></div>
			<div class="row"><div class="{}"; onclick="location.href='?action=on'";>ON</div></div>
			<div class="row"><div class="{}"; onclick="location.href='?action=off'";>OFF</div></div>
			<div class="row"><div class = "value">Requested: {}&deg;</div></div>
			<div class="row"><div class="on"; onclick="location.href='?action=up'";>UP</div></div>
			<div class="row"><div class="on"; onclick="location.href='?action=down'";>DOWN</div></div>
		</div>
	</body>
</html>
		'''
		temp = sensors["room"]["value"]
		self.do_HEAD()
		on="off"
		off="on"
		if state:
			on="on"
			off="off"
		self.wfile.write(html.format(round(float(sensors["room"]["value"])/10,2), on, off, float(sensors["room"]["setPoint"])/10).encode("utf-8"))

	def do_POST(self):
		content_length = int(self.headers['Content-Length'])    # Get the size of data
		post_data = self.rfile.read(content_length).decode("utf-8")   # Get the data
		post_data = post_data.split("=")[1]    # Only keep the value

		if post_data == 'On':
			turnOn()
		elif post_data == 'Off':
			turnOff()
		elif post_data == 'Up':
			incrementRoom(1)
		elif post_data == 'Down':
			incrementRoom(-1)
		self._redirect('/')    # Redirect back to the root url

# Register for button events
button.when_pressed = onButton

# Configure alarm signal handler
signal.signal(signal.SIGALRM, onAlarm)

# Trigger alarm at startup
alarm(1)

http_server = HTTPServer(('rpi4.local', 8000), onHttp)
try:
	http_server.serve_forever()
except KeyboardInterrupt:
	http_server.server_close()

# Main loop - just wait for a signal
while True:
	pause()


