# piPyHeating
A simple heating controller for Raspberry Pi written in Python

## Features

- Control two devices via GPIO (boiler and pump)
- Any quantity of timers
- Each timer has on time, off time and days of week to operate
- Persistent timer configuration
- Visual indication of state via LED
  - Off: Heating off
  - On: Heating on, boiler and pump not active
  - Flashing: Boiler and pump active (heating and water)
  - Pulsing: Boiler oactive, pump not active (hot water only)
- Web interface on port 8000, e.g. http://pi.local:8000
  - Turn heating on and off
  - Adjust room temperature set-point
  - Not yet implemented: Scan and add temperature sensors
  - Add, modify and delete timers
- Amazon Alexa control
  - Turn heating on and off, e.g. "Alexa, turn heating on"

## Installation

This project is designed to run on any Raspberry Pi. (Production unit is a Raspberry Pi 1B.) Raspbian Lite is installed (Buster image from https://www.raspberrypi.org/downloads/raspbian/).

### Hardware
Control of heating is via relays with associated interface circuit, ideally opto-isolated current loop. The relay controller must provide drive current which the Raspbberry Pi sinks by pulling relay interface to GND to operate. Raspberry Pi GPIO is 3.3V so must be protected against over voltage if higher field volts are used, e.g. with series current limit resistor and zener diode across GPIO pin and ground.

Temperature sensors are DS18S20 1-wire devices. There should be one for ambient room temperature and on for water cylinder temperature, attached to cylinder outer wall, approx. 1/3 from bottom. My system uses parsitic power mode, binding power and signal pins together providing 2 wire bus (GND + DATA). A 4K7 pull-up resistor is attached between the bus and +3.3V at the Raspberry Pi end.

Pin | Usage
--- | -----
 1  | 3.3V feed to exteranal components
 5  | Toggle on / off (push to make switch to Gnd)
 6  | 0V (GND) to external components and relay control
 7  | 1-wire bus (4K7 pullup resistor to +3.3V)
 11 | Boiler relay
 12 | Pump relay
 15 | Indication (cathode of LED, anode connected via 4K7 resistor to +3.3V)

### Software
```
sudo apt install python3 python3-pip git
pip3 install gpiozero tornadoweb fauxmo gitpython
cd ~
git clone https://github.com/riban-bw/piPyHeating.git
sudo cp ~/piPyHeating/*.service /etc/systemd/system/
sudo systemctl enable heating
sudo systemctl enable fauxmo
```

Change timers and DS18S20 ids within piPyHeating.py.

```
sudo systemctl restart heating
sudo systemctl restart fauxmo
```

## References
This project stands on the shoulders of these giants:

https://gpiozero.readthedocs.io/en/stable
https://www.tornadoweb.org/en/stable
https://fauxmo.readthedocs.io/en/latest
https://www.raspberrypi.org
https://www.debian.org
