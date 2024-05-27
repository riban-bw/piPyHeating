#!/usr/bin/python3
""" Script to monitor DS18B20 temperature sensor and operate relay at setpoints (with hysteresis)
    Copyright riban <info@riban.co.uk

    Must be run with elevated rights, e.g. as root user (to access GPI interface)
"""

import logging
import os
import glob
import signal
from time import sleep
from gpiozero import LED

RELAY_PIN = 27
SET_POINT_HIGH = 37
SET_POINT_LOW = 35.5

logging.basicConfig (
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)

relay = LED(RELAY_PIN)
running = True
 
os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')
 
base_dir = '/sys/bus/w1/devices/'
device_folder = glob.glob(base_dir + '28*')[0]
device_file = device_folder + '/w1_slave'

def read_temp_raw():
    f = open(device_file, 'r')
    lines = f.readlines()
    f.close()
    return lines

def read_temp():
    try:
        lines = read_temp_raw()
        if lines[0].strip()[-3:] != 'YES':
            logging.warning("Failed to read sensor")
            return
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            temp_string = lines[1][equals_pos+2:]
            temp_c = int(temp_string) // 100
            return temp_c
    except Exception as e:
        if running:
            logging.warning("Cannot read from sensor")
        pass # Can occur when no sensor detected or on close

def signal_handler(sig, frame):
    global running
    if sig in [signal.SIGINT, signal.SIGTERM]:
        running = False

if __name__ == '__main__':
    logging.info("Starting cylinder thermostat monitoring. Deactivating relay")
    relay.on() # Relay is energised when signal is low
    relay_state = False

    catchable_sigs = set(signal.Signals) - {signal.SIGKILL, signal.SIGSTOP}
    for sig in catchable_sigs:
        signal.signal(sig, signal_handler)

    count = 60
    last_temp = 0
    while running:
        sleep(1)
        count += 1
        if count < 60:
            continue
        count = 0
        temp = read_temp()
        if temp is None or temp == last_temp:
            continue
        last_temp = temp
        temp /= 10
        if not relay_state and temp > SET_POINT_HIGH:
            relay.off()
            relay_state = True
            logging.info(f"{temp:0.1f}° - Exceeds high set point ({SET_POINT_HIGH}°). Activating relay.")
        elif relay_state and temp < SET_POINT_LOW:
            relay.on()
            relay_state = False
            logging.info(f"{temp:0.1f}° - Below low set point ({LOW_SET_POINT}°). Deactivating relay.")
        else:
            logging.info(f"{temp:0.1f}°")

    logging.info("Stopping cylinder thermostat monitoring. Deactivating relay")
    relay.on()
