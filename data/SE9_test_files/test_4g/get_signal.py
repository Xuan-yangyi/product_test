# -*- coding: UTF-8 -*-
import serial
import time
import sys
import re

ser = serial.Serial('/dev/ttyUSB2',115200,timeout=1)
ser.write(str('at+csq\r').encode('utf-8'))
time.sleep(0.1)
output = ser.readlines()
if "OK" not in output[-1].decode('utf-8'):
    sys.exit(1)
else:
    csq = output[1].decode('utf-8')
    rssi = re.split(r"\s|,", csq)[1]

ser.write(str('at+cesq\r').encode('utf-8'))
time.sleep(0.1)
output = ser.readlines()
if "OK" not in output[-1].decode('utf-8'):
    sys.exit(1)
else:
    cesq = output[1].decode('utf-8')
    rsrq = re.split(r"\s|,", cesq)[-4]
    rsrp = re.split(r"\s|,", cesq)[-3]

print(rssi, rsrq, rsrp)

ser.close()
sys.exit()
