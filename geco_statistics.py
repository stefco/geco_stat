import sys
import os
import subprocess
import datetime
import numpy as np

class TimeInterval:
    def __init__(self, start, stop):
        #TODO

class Stats:
    def __init__(self, hist_range, bitrate=16384, hist_num_bins=256):

        # make sure hist_range is an ordered pair of numbers
        if not len(hist_range) == 2:
            raise ValueError('second argument (hist_range) must have length 2')
        elif hist_range[0] >= hist_range[1]:
            raise ValueError('minimum value of histogram bin range must be smaller than max')

        self.bitrate = bitrate
        self.hist_num_bins = hist_num_bins
        self.hist_range = hist_range

        self.sum = 0
        self.sum_sq = 0
        self.max = -sys.maxsize - 1
        self.min = sys.maxsize
        self.hist = np.zeros((hist_num_bins, bitrate), dtype=np.int64)
        self.hist_bins = np.linspace(hist_range[0], hist_range[1], hist_num_bins+1)
        self.skipped = () #TODO: should be an Interval type
        self.times = () #TODO: Interval
        self.version = 0.0.0

#TODO: DT and IRIG statistics subclasses
