"""
Program to connect to KiwiSDR, collect signal sampling and to snr evaluation.
Data is stored to RRD (round robin database)
Use snrgraph to prepare graphs

Original Author: Olaf - LA3RK
"""

# Yeah this is all a bit of a mess.

import numpy as np
import struct

from spectra_helpers import *

import datetime
import logging
import socket
import struct
import time
from datetime import datetime
from suntime import Sun
import pathlib

import wsclient

import mod_pywebsocket.common
from mod_pywebsocket.stream import Stream
from mod_pywebsocket.stream import StreamOptions

from optparse import OptionParser

import rrdtool
import sys

parser = OptionParser()
#parser.add_option("-f", "--file", dest="filename", type=str,
#                  help="write waterfall data to binary FILE", metavar="FILE")
parser.add_option("-s", "--server", type=str,
                  help="server name", dest="server", default='192.168.88.200')
parser.add_option("-p", "--port", type=int,
                  help="port number", dest="port", default=8073)
parser.add_option("-a", "--password", type=str,
                  help="server password", dest="password", default='NONE')
parser.add_option("-l", "--length", type=int,
                  help="how many samples to draw from the server", dest="length", default=100)
parser.add_option("-t", "--timestep", type=int,
                  help="Expected timestep between samples", dest="step", default=300)
parser.add_option("--timeout", type=float,
                  help="Connection Timeout", dest="timeout", default=1)
parser.add_option("-z", "--zoom", type=int,
                  help="zoom factor", dest="zoom", default=0)
parser.add_option("-o", "--offset", type=int,
                  help="start frequency in kHz", dest="start", default=0)
parser.add_option("-v", "--verbose", type=int,
                  help="whether to print progress and debug info", dest="verbosity", default=0)
parser.add_option("--spectra", type=str,
                  help="Spectra Output File (csv)", dest="spectra", default='none')

options = vars(parser.parse_args()[0])

if 'filename' in options:
    filename = options['filename']
else:
    filename = None

host = options['server']
port = options['port']
print("KiwiSDR Server: %s:%d" % (host,port))
# the default number of bins is 1024
bins = 1024
print("Number of waterfall bins: %d" % bins)

zoom = options['zoom']
print("Zoom factor:", zoom)

offset_khz = options['start'] # this is offset in kHz

full_span = 30000.0 # for a 30MHz kiwiSDR
if zoom>0:
    span = int(full_span / 2.**zoom)
else:
	span = int(full_span)

rbw = span/bins
if offset_khz>0:
#	offset = (offset_khz-span/2)/(full_span/bins)*2**(zoom)*1000.
	offset = (offset_khz+100)/(full_span/bins)*2**(4)*1000.
	offset = max(0, offset)
else:
	offset = 0

center_freq = int(span/2+offset_khz)
lower_freq = center_freq - span/2
upper_freq = center_freq + span/2
print("Start/End: %.2f / %.2f kHz" % (lower_freq, upper_freq))
snrname = f"{host}_{int(center_freq - span/2)}_{int(center_freq + span/2)}"
snrfile = snrname + ".rrd"
print("Current rrd file: ", snrfile)

snrpath = pathlib.Path(snrfile)
step = options['step']         #Seconds between samples
print(step)
#daystep = 2 * step     #Daily graph stepsize
#weekstep = 7 * daystep    #Weekly graph stepsize
#monthstep = 7 * weekstep  #Monthly graph stepsize
# Define RRD database if not done
if not snrpath.is_file():
    rrdtool.create(
        snrfile,
        #"--source", snrfile,  #snrfile, remove comment and not if recreating
        #"--start", "now",     #start time, uses default now - 10s
        #"--step", "0.3",                    #timestep, adjust crontab accordingly
        f"DS:median:GAUGE:{step*10}:-150:-30",  #Expect readings every 10 step
        f"DS:p95:GAUGE:{step*10}:-150:-30", 
        f"DS:snr:GAUGE:{step*10}:0:60",
        f"RRA:AVERAGE:0.5:5m:1d",   #Daily average
        f"RRA:AVERAGE:0.5:30m:1w",  #Weekly average
        f"RRA:AVERAGE:0.5:3h:30d",  #Monthly average
        f"RRA:MAX:0.1:3h:30d",      #Monthly max
        f"RRA:MIN:0.1:3h:30d",      #Monthly min
        f"RRA:LAST:0.5:1:1")        #Last value
    print("RRD database created: ", snrfile)

now = str.encode(str(datetime.now()))
header = [center_freq, span, now]
#print("Header: ", center_freq, span, now)
#header format; unsigned int (I), unsigned int (i), 26 char array
header_bin = struct.pack("II26s", *header)

print("Trying to contact server...")
try:
    mysocket = socket.socket()
    mysocket.connect((host, port))
    mysocket.settimeout(options['timeout'])
except:
    print("Failed to connect....exit")
    exit(110)   
print("Socket open...")

uri = '/%d/%s' % (int(time.time()), 'W/F')
handshake = wsclient.ClientHandshakeProcessor(mysocket, host, port)
handshake.handshake(uri)

request = wsclient.ClientRequest(mysocket)
request.ws_version = mod_pywebsocket.common.VERSION_HYBI13

stream_option = StreamOptions()
stream_option.mask_send = True
stream_option.unmask_receive = False

mystream = Stream(request, stream_option)
print("Data stream active...")

# send a sequence of messages to the server, hardcoded for now
# max wf speed, no compression
_msg_1 = 'SET auth t=kiwi p='
if options['password'] != 'NONE':
    _msg_1 += options['password']

msg_list = [_msg_1, 'SET zoom=%d start=%d'%(zoom,offset),\
'SET maxdb=0 mindb=-100', 'SET wf_speed=4', 'SET wf_comp=0']
for msg in msg_list:
    mystream.send_message(msg)
print("Starting to retrieve waterfall data...")
# number of samples to draw from server
length = options['length']
# create a numpy array to contain the waterfall data
wf_data = np.zeros((length, bins))
binary_wf_list = []
time = 0
while time<length:
    # receive one msg from server
    try:
        tmp = mystream.receive_message()
    except:
        print("Timeout waiting for data!")
        break

    if str.encode("W/F") in tmp: # this is one waterfall line
        tmp = tmp[16:] # remove some header from each msg
        if options['verbosity']:
            print(time,)
        #spectrum = np.array(struct.unpack('%dB'%len(tmp), tmp) ) # convert from binary data to uint8
        spectrum = np.ndarray(len(tmp), dtype='B', buffer=tmp) # convert from binary data to uint8
        if filename:
            binary_wf_list.append(tmp) # append binary data to be saved to file
        #wf_data[time, :] = spectrum-255 # mirror dBs
        wf_data[time, :] = spectrum
        wf_data[time, :] = -(255 - wf_data[time, :])  # dBm
        wf_data[time, :] = wf_data[time, :] - 13  # typical Kiwi wf cal - NEED TO REVISIT THIS
        time += 1
    else: 
        # this is chatter between client and server
        pass

if time < length:
    print("Did not gather all required samples, abandoning.")

    # Append dummy entry
    if options['spectra'] != 'none':
        append_dummy_entry(options['spectra'],lower_freq, upper_freq, bins)
    
    sys.exit(1)


try:
    mystream.close_connection(mod_pywebsocket.common.STATUS_GOING_AWAY)
    mysocket.close()
except Exception as e:
    print("exception: %s" % e)

avg_wf = np.mean(wf_data, axis=0) # average over time
max_wf = np.max(wf_data, axis=0) # Peak values

wf_dbm = 10*np.log10(np.sum(10**(max_wf/10.0))) - 3

print("Power Sum: %.3f dBm (ADC Overload at -17 dBm)" % wf_dbm)

if options['spectra'] != 'none':
    append_to_file(options['spectra'],lower_freq, upper_freq, bins, avg_wf)

    # Save out peak data
    _max_filename = options['spectra'].split('.')[0] + "_peak." + options['spectra'].split('.')[1]
    append_to_file(_max_filename,lower_freq, upper_freq, bins, max_wf)
    # _output = datetime.utcnow().isoformat() + "Z"
    # for _data in avg_wf:
    #     _output += "," + "%.1f" % _data
    
    # _outspectra = open(options['spectra'],'a')
    # _outspectra.write(_output+"\n")
    # _outspectra.close()

p95 = np.percentile(avg_wf, 95)
median = np.percentile(avg_wf, 50)

print("Average SNR computation...")
print("Waterfall with %d bins: median= %f dB, p95= %f dB - SNR= %f rbw= %f kHz" % (bins, median, p95,p95-median, rbw))
snr = p95-median
data = format("N:%3.1f:%3.1f:%2.2f" % (median,p95,p95-median))


try:	
    rrdtool.update(snrfile, data)
except rrdtool.error as e:
    print("RRD update error: ", e)
lt = rrdtool.last(snrfile)
ft = rrdtool.first(snrfile)
ld = datetime.fromtimestamp(lt)
fd = datetime.fromtimestamp(ft)
print("RRD file %s updated: %s (Unix time: %i)" % (snrfile,ld,lt))

