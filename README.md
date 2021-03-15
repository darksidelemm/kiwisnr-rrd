# KiwiSDR SNR Monitoring Utilities
Based on work by Olaf - LA3RK

## Install Dependencies
This gets it going on a Raspbian system...

* `sudo apt-get install python3-rrdtool rrdtool python3-numpy`
* `sudo pip3 install suntime`


## Running
```
$ python3 snrtorrd.py -s 192.168.88.200 -p 8073
$ python3 rrdtograph.py -s 192.168.88.200
```

(TODO: More usage examples)