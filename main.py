import network
import socket
import time
import rp2
import json
import sys
import re

from machine import Pin

ssid = 'wifi-name'
password = 'wifi-password'
port = 80

# modes 0=OUT; 1=IN; 2=ADC; 3=PWM
pinModes = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,1,1,1,1]
pinNumbers = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,26,27,28]

def sendStatus(cl):
  cl.send('HTTP/1.0 200 OK\r\nContent-type: application/json\r\n\r\n{')
  for i in pinNumbers:
    if pinModes[i]==1:
      cl.send('"p' + str(i) + '":' + str(Pin(i).value()) + ',')
    elif pinModes[i]==2:
      adc = machine.ADC(i)
      cl.send('"p' + str(i) + '":' + str(adc.read_u16()) + ',')
  cl.send('"vbus":' + str(machine.Pin('WL_GPIO2').value()) + '}') # VBUS sense - high if VBUS is present, else low

def setPin(header):
  cl.send('HTTP/1.0 200 OK\r\nContent-type: application/json\r\n\r\n{"Result":"')
  try:
    m = re.match('GET \/setpin\?n=([0-9LED]+)\&m=(\w+)\&v=(\d+)', header)
    if m:
      pinValue = int(m.group(3))
      pinMode = m.group(2)
      if m.group(1) == b'LED':
        Pin('LED').init(mode=Pin.OUT, value=pinValue)
      else:
        pinNum = int(m.group(1))
        pn = Pin(pinNum)

        if pinMode == b'OUT':
          pn.init(mode=Pin.OUT, value=pinValue)
          pinModes[pinNum] = 0
        elif pinMode == b'IN':
          pn.init(mode=Pin.IN)
          pinModes[pinNum] = 1
        elif pinMode == b'ADC':
          machine.ADC(pinNum)
          pinModes[pinNum] = 2
        elif pinMode == b'PWM':
          pwm = machine.PWM(pn)
          pwm.freq(1000);
          pwm.duty_u16(pinValue)
          pinModes[pinNum] = 3
        else:
          raise RuntimeError('unknown mode')
      cl.send('ok')
    else:
     cl.send('wrong url')
  except Exception as e:
    cl.send('error: ' + str(e))
  cl.send('"}')


for i in pinNumbers:
  Pin(i, Pin.IN)

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

# Wait for connect or fail
max_wait = 60
ledPin = Pin('LED', Pin.OUT)
while max_wait > 0:
  ledPin.on()
  if wlan.status() < 0 or wlan.status() >= 3:
    break
  max_wait -= 1
  print('waiting for connection...')
  time.sleep(0.5)
  ledPin.off()
  time.sleep(0.5)

# Handle connection error
if wlan.status() != 3:
  ledPin.on()
  raise RuntimeError('network connection failed')
else:
  print('connected')
  status = wlan.ifconfig()
  print( 'ip = ' + status[0] )

  # Open socket
  addr = socket.getaddrinfo('0.0.0.0', port)[0][-1]

  s = socket.socket()
  s.bind(addr)
  s.listen(1)

  print('listening on', addr)
  ledPin.off()

  rePageUrl = re.compile("^GET \/(\w+)")
  
# Listen for connections
while True:
  try:
    cl, addr = s.accept()
    print('client connected from', addr)
    cl_file = cl.makefile('rwb', 0)
    firstLine = cl_file.readline()
    while True:
      line = cl_file.readline()
      if not line or line == b'\r\n':
        break
   
    m = rePageUrl.match(firstLine)
    pageName = ''
    if m:
      pageName = m.group(1)
    #print('pageName:', pageName)
    if pageName == b'status':
      sendStatus(cl)
    elif pageName == b'setpin':
      setPin(firstLine)
    else:
      cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
      f = open('index.htm', 'r')
      myline = f.readline()
      while myline:
        cl.send(myline)
        myline = f.readline()
      f.close()  
    cl.close()

  except OSError as e:
    cl.close()
    print('connection closed')
