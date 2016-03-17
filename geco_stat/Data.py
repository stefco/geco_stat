# -*- coding: utf-8 -*-

import abc
import numpy as np      # >=1.10.4
from geco_stat._version import __version__
from geco_stat._constants import __default_bitrate__
from geco_stat.Abstract import Factory
from geco_stat.Abstract import AbstUnionable
from geco_stat.Abstract import AbstractPlottable
from geco_stat.Abstract import HDF5_IO
from geco_stat.Time import TimeIntervalSet

# Inherit from HDF5_IO first in order to get an implemented clone method
class AbstData(HDF5_IO,
                         # AbstractPlottable, TODO Make AbstractPlottable
                         AbstUnionable):
    """
    Abstract class for data that can be aggregated. Subclasses should represent
    small, conceptually unified collections of information. For example,
    a subclass of AbstData might focus exclusively on gathering
    basic statistics, like the mean and median values of a periodic timeseries.
    
    As of this writing, AbstData DOES NOT necessarily store time
    information, since time information might not be necessary for every
    single type of ReportData. This is very much subject to change.
    """
    __metaclass__  = abc.ABCMeta
    __version__ = __version__

# TODO: Make AbstractPlottable
class Histogram(AbstData):
    """
    A class for storing a histogram of (quasi) periodic timeseries. In
    the current version, each period is assumed to last for one second.
    Bitrate is adjustable. The idea is to compare many periods worth
    of a signal in order to determine how much the signal varies over
    the entire timespan considered.

    This class DOES NOT contain information about the time ranges
    included in the data; that information should go into some containing
    class. This class is intended as a diagnostic report primitive.
    """

    def __init__(self,
                 hist            = None,
                 hist_range      = (-1e3, 1e3),
                 hist_num_bins   = 256,
                 bitrate         = __default_bitrate__):
        """
        Initialize an instance of the class. All properties have default
        values corresponding to an empty statistics set; they can be
        individually overridden.
        """
        # make sure hist_range is an ordered pair of numbers
        if not len(hist_range) == 2:
            raise ValueError('second argument (hist_range) must have length 2')
        elif hist_range[0] >= hist_range[1]:
            raise ValueError('min val of hist bin range must be less than max')

        # set values to "empty" histograms
        if hist is None:
            hist = np.zeros((hist_num_bins, bitrate), dtype=np.int64)

        assert np.int64(hist_num_bins) == hist_num_bins, \
            'hist_num_bins must be an integer'
        self.hist_num_bins  = np.int64(hist_num_bins)
        assert len(hist_range) == 2
        self.hist_range     = np.array(hist_range)
        # Make sure this is a copy of the data
        self.hist           = np.array(hist, copy=True)
        self.hist_bins      = np.linspace(hist_range[0], hist_range[1],
                                          hist_num_bins+1)
        self.t_ticks        = np.linspace(0,1,bitrate+1)
        assert np.int64(bitrate) == bitrate, 'bitrate must be an integer'
        self.bitrate        = np.int64(bitrate)

    def __union__(self, other):
        """
        Take the union of these two histograms, representing the histogram of
        the union of the two histograms' respective datasets.
        """
        ans         = self.clone()
        ans.hist    = self.hist + other.hist
        return ans

    def __clone__(self):
        return type(self)(
            hist            = self.hist,
            hist_range      = self.hist_range,
            hist_num_bins   = self.hist_num_bins,
            bitrate         = self.bitrate
        )

    def assert_unionable(self, other):
        if (self.hist_range != other.hist_range or
                self.hist_num_bins != other.hist_num_bins):
            raise ValueError('Histograms have different bin edges')
        if self.bitrate != other.bitrate:
            raise ValueError('Histograms have different bitrates')
        if self.__version__ != other.__version__:
            raise ValueError('Histograms have different versions')
        if not isinstance(self, type(other)):
            raise ValueError('Type mismatch: cannot union ' +
                             str(type(self)) + ' with ' + str(type(other)))
        return True

    def assert_self_consistent(self):
        if self.__version__ != __version__:
            raise ValueError(
                'Histogram version ' +
                self.__version__ +
                ' does not match lib version')
        assert self.hist_bins == np.linspace(
            self.hist_range[0], self.hist_range[1], self.hist_num_bins+1)
        assert self.t_ticks == np.linspace(0,1,self.bitrate+1)
        assert np.int64(
            self.bitrate) == self.bitrate, 'bitrate must be an integer'
        return True

    @classmethod
    def __from_dict__(cls, d):
        return cls(
            hist            = d['hist'],
            hist_range      = d['hist_range'],
            hist_num_bins   = d['hist_num_bins'],
            bitrate         = d['bitrate']
        )

    def __to_dict__(self):
        return {
            'hist': np.array(self.hist),
            'hist_range': np.array(self.hist_range),
            'hist_num_bins': self.hist_num_bins,
            'bitrate': self.bitrate,
            'version': self.__version__,
            'class': 'Histogram'
        }

    def from_timeseries(self, timeseries):
        num_sec = timeseries.get_num_seconds()
        hist, xedges, yedges = np.histogram2d(
            timeseries.flatten(),
            np.tile(self.t_ticks, num_sec),
            bins = [self.hist_bins, self.t_ticks])
        assert xedges == self.hist_bins, \
            'xedges should be the histogram bins'
        assert yedges == self.t_ticks, \
            'yedges should be the t_ticks'
        assert self.bitrate == timeseries.bitrate, \
            'timeseries and histogram must have same bitrate'
        self.assert_self_consistent()
        return type(self)(
            hist            = hist,
            hist_range      = self.hist_range,
            hist_num_bins   = self.hist_num_bins,
            bitrate         = self.bitrate)

    def __eq__(self, other):
        if (self.hist_range != other.hist_range or
                self.hist_num_bins != other.hist_num_bins):
            return False
        if self.bitrate != other.bitrate:
            return False
        if self.__version__ != other.__version__:
            return False
        if not isinstance(self, type(other)):
            return False
        return np.array_equal(self.hist, other.hist)

# TODO: Make AbstractPlottable
class Statistics(AbstData):
    """
    A class for storing diagnostic statistics for the aLIGO timing system.
    Includes methods for iteratively generating, amalgamating, and
    displaying statistics.

    This class DOES NOT contain information about the time ranges
    included in the data; that information should go into some containing
    class. This class is intended as a diagnostic report primitive.
    """

    def __init__(self,
                 sum             = None,
                 sum_sq          = None,
                 max             = None,
                 min             = None,
                 num             = 0,
                 bitrate         = __default_bitrate__):
        """
        All properties have default values corresponding to an empty statistics
        set; they can be individually overridden.
        """
        # set values of sum, sum_sq, and the histograms, since these depend on
        # bitrate and hist_num_bins and hence cannot be set above
        if sum is None:
            sum        = np.zeros(bitrate)
        if sum_sq is None:
            sum_sq     = np.zeros(bitrate)
        if max is None:
            # lowest possible max, cannot survive
            max        = np.ones(bitrate) * np.finfo(np.float64).min
        if min is None:
            min        = np.ones(bitrate) * \
                np.finfo(np.float64).max # same for min

        self.sum        = np.array(sum, copy=True).reshape((bitrate,))
        self.sum_sq     = np.array(sum_sq, copy=True).reshape((bitrate,))
        self.max        = np.array(max, copy=True).reshape((bitrate,))
        self.min        = np.array(min, copy=True).reshape((bitrate,))
        assert np.int64(
            num) == num, 'must provide an integer number of previous seconds'
        self.num        = np.int64(num)
        assert np.int64(bitrate) == bitrate
        self.bitrate    = np.int64(bitrate)

        self.assert_self_consistent()

    def __union__(self, other):
        """
        Take the union of these statistics, representing the same statistics
        taken on the union of the two statistics objects' respective datasets.
        """
        ans         = self.clone()
        ans.sum     = self.sum      + other.sum
        ans.sum_sq  = self.sum_sq   + other.sum_sq
        ans.max     = self.max      + other.max
        ans.min     = self.min      + other.min
        ans.num     = self.num      + other.num
        return ans

    def __clone__(self):
        self.assert_self_consistent()
        return type(self)(
            sum             = self.sum,
            sum_sq          = self.sum_sq,
            max             = self.max,
            min             = self.min,
            num             = self.num,
            bitrate         = self.bitrate
        )

    def assert_unionable(self, other):
        if self.bitrate != other.bitrate:
            raise ValueError('Statistics have different bitrates')
        if self.__version__ != other.__version__:
            raise ValueError('Statistics have different versions')
        if not isinstance(self, type(other)):
            raise ValueError('Type mismatch: cannot union ' +
                             str(type(self)) + ' with ' + str(type(other)))
        return True

    def assert_self_consistent(self):
        assert self.sum.shape == (self.bitrate,), \
            "sum should be vector with length equal to bitrate"
        assert self.sum_sq.shape == (self.bitrate,), \
            "sum_sq should be vector with length equal to bitrate"
        assert self.max.shape == (self.bitrate,), \
            "max should be vector with length equal to bitrate"
        assert self.min.shape == (self.bitrate,), \
            "min should be vector with length equal to bitrate"
        assert np.int64(self.num) == self.num
        assert np.int64(self.bitrate) == self.bitrate, \
            "bitrate must be an integer"
        if self.__version__ != __version__:
            raise ValueError(
                'Statistics version ' +
                self.__version__ +
                ' does not match lib version')
        if not ((self.bitrate,) == self.sum.shape ==
                self.sum_sq.shape == self.max.shape == self.min.shape):
            raise ValueError('Statistics fields must be 1-D with length equal '
                             'to bitrate')
        return True

    @classmethod
    def __from_dict__(cls, d):
        return cls(
            sum     = d['sum'],
            sum_sq  = d['sum_sq'],
            max     = d['max'],
            min     = d['min'],
            num     = d['num'],
            bitrate = d['bitrate']
        )

    def __to_dict__(self):
        assert self.num == np.int64(self.num)
        return {
            'sum':      np.array(self.sum).flatten(),
            'sum_sq':   np.array(self.sum_sq).flatten(),
            'max':      np.array(self.max).flatten(),
            'min':      np.array(self.min).flatten(),
            'num':      np.int64(self.num),
            'bitrate':  np.int64(self.bitrate),
            'version':  self.__version__,
            'class':    'Statistics'
        }

    def from_timeseries(self, timeseries):
        self_type = type(self)
        return self_type(
            sum     = timeseries.sum(0),
            sum_sq  = np.power(timeseries, 2).sum(0),
            max     = np.max(timeseries, 0),
            min     = np.min(timeseries, 0),
            num     = timeseries.shape[0],
            bitrate = timeseries.bitrate)

    def __eq__(self, other):
        if self.bitrate != other.bitrate:
            return False
        if self.__version__ != other.__version__:
            return False
        if not isinstance(self, type(other)):
            return False
        return (
            np.array_equal(self.sum,    other.sum)      and
            np.array_equal(self.sum_sq, other.sum_sq)   and
            np.array_equal(self.max,    other.max)      and
            np.array_equal(self.min,    other.min)      and
            np.array_equal(self.num,    other.num)
        )

# TODO: Add a ReportData wrapper for slow channel timeseries, complete with
# plotting

Factory.add_class(Histogram)
Factory.add_class(Statistics)
