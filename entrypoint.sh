#!/usr/bin/env bash
set -e
if [  $# -ne 4 ] 
then 
    echo "Usage: hostname port name password"
    exit 1
fi 
# Capture Data
python3 /app/snrtorrd.py -s $1 -p $2 -a $4 --spectra=$1_spectra.csv
# Produce RRD Plots
python3 /app/rrdtograph.py -s $1 --title "$3"
# Produce Spectrograph and RX Power plots
python3 /app/kiwi_spectrum_plot.py --hours 72 --spectrograph $1_spectro.png --title "$3"  --rxpower $1_rxpower.png $1_spectra.csv
python3 /app/kiwi_spectrum_plot.py --hours 72 --title "$3"  --rxpower $1_rxpower.png $1_spectra_peak.csv

mv *.png /output