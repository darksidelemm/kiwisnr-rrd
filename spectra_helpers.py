#
#   Helper functions to deal with saved spectra data.
#
import datetime
import os.path
import numpy as np
from dateutil.parser import parse


def create_new_file(filename, lower_freq, upper_freq, bins):
    """ Create a new spectra data file with a header """
    _f = open(filename,'w')
    _header = f"#SPECTRA,{lower_freq:.1f},{upper_freq:.1f},{bins:.1f}\n"
    _f.write(_header)
    _f.close()


def get_file_header(filename):
    _f = open(filename,'r')
    try:
        _header = _f.readline()[1:] # Strip off leading #
        _f.close()
        _fields = _header.split(',')
        if _fields[0] != 'SPECTRA':
            print("Not a Spectra File!")
            return None
        else:
            _lower_freq = float(_fields[1])
            _upper_freq = float(_fields[2])
            _bins = float(_fields[3])

            return (_lower_freq, _upper_freq, _bins)
    except Exception as e:
        print(f"Error reading spectra file - {str(e)}")
        return None


def read_spectra_file(filename, time_limit = None):
    """ Attempt to read in a spectra data file """
    _header = get_file_header(filename)

    if _header is None:
        return None
    
    _now = datetime.datetime.now(datetime.timezone.utc)

    _f = open(filename,'r')
    _f.readline() # Discard first line
    
    _times = []
    _spectra = []

    for line in _f:
        _fields = line.split(',')
        _time = parse(_fields[0])

        if time_limit:
            _delta = abs((_now - _time).total_seconds())
            if _delta > (time_limit*3600):
                continue

        _spec = [float(i) for i in _fields[1:]]

        _spectra.append(_spec)
        _times.append(_time)
    
    return {'lower': _header[0], 'upper':_header[1], 'time':_times, 'spectra':np.array(_spectra)}


def clip_spectra_file(filename, time_limit=48):
    """ Read in a spectra file, remove any entries outside of a provided time bounds, then write it back out """
    _header = get_file_header(filename)

    if _header is None:
        return None

    _now = datetime.datetime.now(datetime.timezone.utc)    

    # Output data.
    _outdata = ""

    _f = open(filename, 'r')
    _header = _f.readline()
    _outdata += _header

    for line in _f:
        _fields = line.split(',')
        _time = parse(_fields[0])

        _delta = abs((_now - _time).total_seconds())
        if _delta > (time_limit*3600):
            continue
        else:
            _outdata += line
    
    _f.close()

    # Re-open file for writing.
    _f = open(filename, 'w')
    _f.write(_outdata)
    _f.close()


def append_to_file(filename, lower_freq, upper_freq, bins, data):
    """ Attempt to append a data array (np array) to a file """

    if not os.path.isfile(filename):
        # File doesn't exist - create it.
        create_new_file(filename, lower_freq, upper_freq, bins)
    else:
        # Attempt to read in the header line.
        _header = get_file_header(filename)
        if _header is not None:
            if (_header[0] != lower_freq) or (_header[1] != upper_freq) or (_header[2] != bins):
                print("Header mismatch!")
                return
        else:
            print("Could not read header!")
            return
    
    # Now we can append the line.
    _output = datetime.datetime.utcnow().isoformat() + "Z"
    for _data in data:
        _output += "," + "%.1f" % _data
    _output += "\n"

    _f = open(filename, 'a')
    _f.write(_output)
    _f.close()


def append_dummy_entry(filename, lower_freq, upper_freq, bins):
    # Append a dummy entry, indicating we didn't get any data.
    _data = np.ones(bins)*-999.0

    append_to_file(filename, lower_freq, upper_freq, bins, _data)