#
#  KiwiSDR Long Duration Spectrum Plot
#
import argparse
import logging
import sys
import numpy as np

# Headless operation
import matplotlib as mpl
mpl.use('Agg')

import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from dateutil.parser import parse

from spectra_helpers import *

# Defaults
FREQ_MIN = 0
FREQ_MAX = 30000


def calculate_total_power(spectra):
    """ Calculate an estimate of the total power into the KiwiSDR """

    _spectra_mw = 10**(spectra/10)
    _timeseries = np.sum(_spectra_mw, axis=1)

    return 10*np.log10(_timeseries)


def main():
    # Read command-line arguments
    parser = argparse.ArgumentParser(description="KiwiSDR Spectrum Plotter", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('filename', type=str, help="KiwiSDR Spectrum Log File (CSV)")
    parser.add_argument("--hours", type=int, default=72, help="How many hours to plot.")
    parser.add_argument("--cmap_min", type=float, default=-110, help="Colormap Minimum Value (dBm)")
    parser.add_argument("--cmap_max", type=float, default=-30, help="Colormap Maximum Value (dBm)")
    parser.add_argument("--clip", action="store_true", default=False, help="Clip file to the hour limit specified with --hours")
    parser.add_argument('--spectrograph', type=str, default=None, help="Save Spectrograph to this file.")
    parser.add_argument('--rxpower', type=str, default=None, help="Save RX Power Plot to this file.")
    parser.add_argument("--title", type=str, default="KiwiSDR", help="KiwiSDR Name (for plot titles)")
    parser.add_argument("-v", "--verbose", action="store_true", default=False, help="Verbose output (set logging level to DEBUG)")
    args = parser.parse_args()

    if args.verbose:
        logging_level = logging.DEBUG
    else:
        logging_level = logging.INFO

    # Set up logging
    logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging_level)


    # Read in file
    _data = read_spectra_file(args.filename, time_limit = args.hours)

    if args.clip:
        clip_spectra_file(args.filename, time_limit=args.hours)
        print(f"Clipped Spectra file to {args.hours} hours backlog.")

    if _data is None:
        print("Spectra file unreadable!")
        sys.exit(1)
    
    times = _data['time']
    spectra = _data['spectra']
    freq_lower = _data['lower']/1000.0
    freq_upper = _data['upper']/1000.0

    _rx_power = calculate_total_power(spectra)

    # Date formatter we'll use on both plots
    dtFmt = mdates.DateFormatter('%Y-%m-%d %H')

    # Plot Total Power vs time
    fig, ax = plt.subplots(figsize=(12,3))
    ax.plot(times, _rx_power)
    ax.set_xlabel("Time")
    ax.set_ylabel("RX Power Estimate (dBm)")
    fig.autofmt_xdate()
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(dtFmt)
    ax.grid()
    plt.title(f"{args.title} RX Power")

    if args.rxpower:
        plt.savefig(args.rxpower, dpi=300, bbox_inches='tight')
    

    # Plot Spectra
    fig, ax = plt.subplots(figsize=(12,6))

    x_lims = mdates.date2num(times)

    spec = ax.imshow(np.flipud(spectra.T), cmap=plt.cm.jet, vmin=args.cmap_min, vmax=args.cmap_max, extent=[x_lims[0],x_lims[-1],freq_lower,freq_upper])
    ax.set_ylabel("Frequency (MHz)")
    ax.set_xlabel("Time (UTC)")
    fig.autofmt_xdate()
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(dtFmt)
    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=360))
    ax.set_aspect(0.05)
    plt.title(f"{args.title} Spectrograph")
    fig.colorbar(spec, ax=ax, shrink=0.8, label="Power (dBm / bin)")

    if args.spectrograph:
        plt.savefig(args.spectrograph, dpi=300, bbox_inches='tight')



if __name__ == "__main__":
    main()