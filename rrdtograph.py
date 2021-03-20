"""
Program to make graphs from rrd bases prepared by snrtorrd.py
Data is stored to RRD (round robin database)
Use snrgraph to prepare graphs

Original Author: Olaf - LA3RK
"""
import numpy as np
import struct

import array
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

parser = OptionParser()
parser.add_option("-s", "--server", type=str,
                  help="server name", dest="server", default='192.168.88.200')
parser.add_option("-t", "--timestep", type=int,
                  help="Expected timestep between samples", dest="step", default=300)
parser.add_option("-z", "--zoom", type=int,
                  help="zoom factor", dest="zoom", default=0)
parser.add_option("-o", "--offset", type=int,
                  help="start frequency in kHz", dest="start", default=0)
parser.add_option("--title", type=str,
                  help="KiwiSDR Name", dest="title", default="KiwiSDR")
parser.add_option("-v", "--verbose", type=int,
                  help="whether to print progress and debug info", dest="verbosity", default=0)

options = vars(parser.parse_args()[0])

if 'filename' in options:
    filename = options['filename']
else:
    filename = None

host = options['server']

zoom = options['zoom']

offset_khz = options['start'] # this is offset in kHz

full_span = 30000.0 # for a 30MHz kiwiSDR
if zoom>0:
    span = int(full_span / 2.**zoom)
else:
	span = int(full_span)

bins = 1024
rbw = span/bins
if offset_khz>0:
	offset = (offset_khz+100)/(full_span/bins)*2**(4)*1000.
	offset = max(0, offset)
else:
	offset = 0

center_freq = int(span/2+offset_khz)
rrdname = f"{host}_{int(center_freq - span/2)}_{int(center_freq + span/2)}"
snrfile = rrdname + ".rrd"
print("Current rrd file: ", snrfile)

snrpath = pathlib.Path(snrfile)
step = options['step']         #Seconds between samples
daystep = 2 * step     #Daily graph stepsize
weekstep = 7 * daystep    #Weekly graph stepsize
monthstep = 7 * weekstep  #Monthly graph stepsize

#Prepare graph
#Current date/time/midnight/sunset/sunrise
ct = datetime.utcnow()
ct = ct.strftime("%Y-%m-%d %H:%M")
print("Preparing graphs: ",ct)
#Calc epoch of last midnight - need correction for local time ( - 1 hour)
lt = rrdtool.last(snrfile)
print("Last rrdupdate: ",lt)
ld = datetime.fromtimestamp(lt)
print("RRD file last updat: %s (Unix time: %i)" % (ld,lt))
mn = int(lt) // 86400 * 86400 - 3600
sun = Sun(59,10)  #Change to location
sr = int(sun.get_sunrise_time().timestamp())
ss = int(sun.get_sunset_time().timestamp())
if lt < ss: ss = ss - 24*3600
for sched in ['Daily' , 'Weekly', 'Monthly']:
    ssb = mnb = srb = "VRULE:0#000000"
    ssc = src = "COMMENT:"
    print("Preparing graph: ", snrfile, "-", sched)
    if sched == 'Weekly':
        period = "w"
        per = ["COMMENT:\rAverage SNR\: ",
              "GPRINT:snr_avg:%2.1lf dB",
              "COMMENT:Max SNR\: ",
              "GPRINT:snr_max:%2.1lf dB",
              "COMMENT:Min SNR\: ",
              "GPRINT:snr_min:%2.1lf dB"]
    elif sched == 'Daily':
        period = "d"
        per = ["COMMENT:Last SNR\: ",
              "GPRINT:snr_last:%2.1lf dB",]
              #f"VRULE:{ss}#00008b",
              #"COMMENT:Blue bar\:Sunset",
              #f"VRULE:{mn}#0000FF:dashes",
              #f"VRULE:{sr}#FF4500",
              #"COMMENT:Red bar\:Sunrise"]
    elif sched == 'Monthly':
        period = "m"
        per = ["COMMENT:\rAverage SNR\: ",
              "GPRINT:snr_avg:%2.1lf dB",
              "COMMENT:Max SNR\: ",
              "GPRINT:snr_max:%2.1lf dB",
              "COMMENT:Min SNR\: ",
              "GPRINT:snr_min:%2.1lf dB"]
    gr = ["--start", "-1%s" %(period),         #Start -1d / - 1w / -1m
         "--vertical-label=Signal levels (dBm/bin)",
         "--right-axis=0.5:60",               #Define right axis
         "--right-axis-label=SNR (dB)",
         "--upper-limit=-40",
         "--lower-limit=-120",
         f"--watermark=areg.org.au - {ct}",
         "--width=500",
         "--height=300",
         f"--title={options['title']}, {sched} from: {int(offset_khz)} - {int(offset_khz + span)} kHz, {rbw:.2f} kHz RBW",
         #"HRULE:-100#000000",                      #-100 dB ref line
         "DEF:m1_num=" + snrfile + ":p95:AVERAGE",
         "DEF:m2_num=" + snrfile + ":median:AVERAGE",
         "DEF:m3_num=" + snrfile + ":snr:AVERAGE",
         "DEF:m4_num=" + snrfile + ":snr:MAX",
         "DEF:m5_num=" + snrfile + ":snr:MIN",
         "VDEF:snr_last=m3_num,LAST",
         "VDEF:snr_avg=m3_num,AVERAGE",
         "VDEF:snr_max=m4_num,MAXIMUM",
         "VDEF:snr_min=m5_num,MINIMUM",
         "CDEF:m3_shifted=m3_num,2,*,120,-",       #Shift SNR to right axis
         #f"CDEF:eve=m3_shifted,60,MAXNAN,{ss},TIME,LE,*",  #Prepare area for night
         #f"CDEF:mrn=m3_shifted,60,MAXNAN,{sr},TIME,GE,*",
         #f"CDEF:night=eve,mrn,MAX,120,-",
         #"AREA:night#d3d3d3:Night",
         "LINE1:m1_num#0000FF:95th Percentile",
         "LINE1:m2_num#00FF00:Median level",
         "LINE2:m3_shifted#FF0000:SNR"]
    rrdtool.graph(f"{rrdname}-{sched}.png",gr+per)

print("All done!")
