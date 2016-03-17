# -*- coding: utf-8 -*-

import os
import abc
import numpy as np      # >=1.10.4
from geco_stat._version import __version__, __release__
from geco_stat._constants import __default_bitrate__
from geco_stat.Abstract import Factory
from geco_stat.Abstract import AbstUnionable
from geco_stat.Abstract import AbstractPlottable
from geco_stat.Abstract import HDF5_IO
from geco_stat.Report import AbstReport
from geco_stat.Data import AbstData
from geco_stat.Data import Statistics
from geco_stat.Data import Histogram
from geco_stat.Time import TimeIntervalSet
from geco_stat.Timeseries import Timeseries

def run_unit_tests():
    print('Testing class initializations.')
    Timeseries((16384,))
    TimeIntervalSet()
    Histogram()
    Statistics()

    # TODO: make a timeseries and then from there unit test everything else

    print('Testing TimeIntervalSet arithmetic.')
    ti = TimeIntervalSet
    assert ti([66,69]) + ti([67,72]) == ti([66,72]), "Union failing"
    assert ti([66,69]) * ti([67,72]) == ti([67,69]), "Intersection failing"
    assert ti([66,69]) + ti([70,72]) == ti([66,69,70,72]), "Union failing"
    assert ti([66,73]) - ti([67,72]) == ti([66,67,72,73]), "Complement failing"
    assert ti([66,73]) - ti([66,73]) == ti(), "Complement failing"
    # TODO: Add some more arithmetic assertions.

    print('Testing TimeIntervalSet frame time rounding.')
    assert ti([65,124]).round_to_frame_times() == ti([64, 128]), \
        "Rounding to frame times is failing"
    assert ti([64,128]).round_to_frame_times() == ti([64, 128]), \
        "Rounding to frame times is failing"
    assert ti([63,65,120,133]).round_to_frame_times() == ti([0,192]), \
        "Rounding to frame times is failing"

    print('Testing TimeIntervalSet length calculation.')
    assert ti([6400,6464]).combined_length() == 64, \
        'Time interval total length calculations are off'
    assert ti([0,4,6400,6466]).combined_length() == 70, \
        'Time interval total length calculations are off'

    print('Testing TimeIntervalSet splitting into frame files.')
    try:
        # this should raise a value error since the frame times are not rounded
        ti([66,68]).split_into_frame_file_intervals()
        raise AssertionError('Should not be able to split a time interval not '
                             'having round endpoints')
    except ValueError:
        pass

    print('Testing HDF5 file saving capabilities.')
    ex = {
        'name': 'stefan',
        'age':  np.int64(24),
        'fav_numbers': np.array([2,4,4.3]),
        'fav_tensors': {
            'levi_civita3d': np.array([
                [[0,0,0],[0,0,1],[0,-1,0]],
                [[0,0,-1],[0,0,0],[1,0,0]],
                [[0,1,0],[-1,0,0],[0,0,0]]
            ]),
            'kronecker2d': np.identity(3)
        }
    }
    AbstReport.__save_dict_to_hdf5__(
        ex, 'geco_statistics_test_hdf5_dict_example.hdf5')
    loaded = AbstReport.__load_dict_from_hdf5__(
        'geco_statistics_test_hdf5_dict_example.hdf5')
    os.remove('geco_statistics_test_hdf5_dict_example.hdf5')
    np.testing.assert_equal(loaded, ex)

    # TODO: Add in tests for creating time intervals from strings
    # TODO: Add in HDF5 save/load tests for all classes

    clean_up()
    print('Unit tests passed!')


def clean_up():
    """
    Clean up side-effects after unit and integration tests have been run.
    """
    if os.path.exists('geco_statistics_test_hdf5_dict_example.hdf5'):
        os.remove('geco_statistics_test_hdf5_dict_example.hdf5')

