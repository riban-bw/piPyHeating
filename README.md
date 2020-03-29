# piPyHeating
A simple heating controller for Raspberry Pi written in Python

##Features

- Control two devices via GPIO (boiler and pump)
- Any quantity of timers
- Each timer has on time, off time and days of week to operate
- Visual indication of state via LED:
-- Off: Heating off
-- On: Heating on, boiler and pump not active
-- Flashing: Boiler and pump active (heating and water)
-- Pulsing: Boiler oactive, pump not active (hot water only)
- Web interface on port 8000, e.g. http://pi.local:8000
-- Turn heating on and off
-- Adjust room temperature set-point
- Amazon Alexa control:
-- Turn heating on and off, e.g. "Alexa, turn heating on"

##Installation

This project is designed to run on any Raspberry Pi. (Production unit is a Raspberry Pi 1B.) Raspbian Lite is installed (Buster image from https://www.raspberrypi.org/downloads/raspbian/).

Pin | Usage
--- | -----
 1  | 3.3V feed to exteranal components
 6  | 0V (Gnd) to external components and relay control
 7  | 1-wire bus (4K7 pullup resistor to +3.3V)
 11 | Boiler relay
 12 | Pump relay
 13 | Toggle on / off (push to make switch to Gnd)
 15 | Indication (cathode of LED, anode connected via 4K7 resistor to +3.3V)
 
```
sudo apt install python3 python3-pip
pip3 install gpiozero tornadoweb fauxmo git
cd ~
git clone https://github.com/riban-bw/piPyHeating.git
sudo cp ~/piPyHeating/*.service /etc/systemd/system/
sudo systemctl enable heating
sudo systemctl enable fauxmo
```
