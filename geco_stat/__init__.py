# -*- coding: utf-8 -*-

import os
import abc
import numpy as np      # >=1.10.4
from geco_stat._version import __version__, __release__
from geco_stat._constants import __default_bitrate__
from geco_stat.Interface import ReportInterface
from geco_stat.Time import TimeIntervalSet
from geco_stat.Exceptions import VersionException, MissingChannelDataException
from geco_stat.Timeseries import Timeseries


# could use the interval package, but would be one more external dependency

# TODO: this should probably not subclass ReportInterface, unless I can think
# of some reason why the file I/O features of ReportInterface would be
# independently valuable here.
class PlottableInterface(ReportInterface):
    """
    An interface for generating matplotlib figures that can be used in
    visualizing data.
    """
    __metaclass__  = abc.ABCMeta

    @abc.abstractmethod
    def plot(self):
        """
        Create some sort of visualization for the information content of this
        object. Container objects should use this to
        recursively call plotting functions in their constituents and generate
        summary plots representing all their information.
        """

    @abc.abstractmethod
    def summary(self):
        """
        Create some sort of verbose, human-readable text summary for the
        information content of this object. Should return a string.
        """

# TODO: Make PlottableInterface


class AbstractReportData(ReportInterface):
    """
    Abstract class for aggregated data. All instances must implement interface.
    """
    __metaclass__  = abc.ABCMeta

# TODO: Make PlottableInterface


class Histogram(AbstractReportData):
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
                 bitrate         = __default_bitrate__,
                 version         = __version__):
        """
        Initialize an instance of the class. All properties have default
        values corresponding to an empty statistics set; they can be
        individually overridden.
        """
        # make sure hist_range is an ordered pair of numbers
        if not len(hist_range) == 2:
            raise ValueError('second argument (hist_range) must have length 2')
        if version != self.__version__:
            raise VersionException()
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

    def _confirm_unionability(self, other):
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

    def _assert_self_consistent(self):
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
            bitrate         = d['bitrate'],
            version         = d['version']
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
        self._assert_self_consistent()
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

# TODO: Make PlottableInterface


class Statistics(AbstractReportData):
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
                 bitrate         = __default_bitrate__,
                 version         = __version__):
        """
        All properties have default values corresponding to an empty statistics
        set; they can be individually overridden.
        """
        if version != self.__version__:
            raise VersionException()

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

        self._assert_self_consistent()

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
        self._assert_self_consistent()
        return type(self)(
            sum             = self.sum,
            sum_sq          = self.sum_sq,
            max             = self.max,
            min             = self.min,
            num             = self.num,
            bitrate         = self.bitrate
        )

    def _confirm_unionability(self, other):
        if self.bitrate != other.bitrate:
            raise ValueError('Statistics have different bitrates')
        if self.__version__ != other.__version__:
            raise ValueError('Statistics have different versions')
        if not isinstance(self, type(other)):
            raise ValueError('Type mismatch: cannot union ' +
                             str(type(self)) + ' with ' + str(type(other)))
        return True

    def _assert_self_consistent(self):
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
            bitrate = d['bitrate'],
            version = d['version']
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

# TODO: Make PlottableInterface


class AbstractReport(ReportInterface):
    """
    A class for generating reports on data integrity. Should be extended to
    create reports specific to different types of data, e.g. IRIGBReport
    and DuoToneReport.

    The AbstractReport class contains information on the time intervals included
    as well as basic statistics (mean, max, min, standard deviation)
    on the time intervals included, and finally, multiple histograms
    covering multiple "zoom" levels, for a tailored view of the data.

    Arguments:
    bitrate         the bitrate of the signal considered. defaults to 16384.

    time_intervals  the time intervals over which the data used to create
                    the report were recorded. defaults to an empty time
                    interval.

    data            a dictionary containing ReportData objects. defaults to
                    an empty histogram and an empty statistics instance with
                    the same bitrate.
    """
    __metaclass__  = abc.ABCMeta

    def __init__(self,
                 bitrate         = __default_bitrate__,
                 version         = __version__,
                 time_intervals  = None,
                 data            = None):

        if version != self.__version__:
            raise VersionException()

        assert np.int64(bitrate) == bitrate, 'bitrate must be an integer'
        self.bitrate = np.int64(bitrate)
        if time_intervals is None:
            self.time_intervals = TimeIntervalSet()
        else:
            self.time_intervals = time_intervals.clone()

        if data is None:
            data = self.__report_data_prototype__(bitrate)
        self._data = data           # data grouped here
        for key in data:            # instance attr pointers for convenience
            if hasattr(self, key):
                raise ValueError('AbstractReportData dictionary should not '
                                 'have attributes conflicting with '
                                 'AbstractReport attributes.')
            setattr(self, key, data[key])
        self._assert_self_consistent()

    @classmethod
    @abc.abstractmethod
    def __report_data_prototype__(cls, bitrate=__default_bitrate__):
        """
        MUST BE A CLASSMETHOD.

        Returns an empty ReportData._data dictionary representative of this
        ReportSet subclass. The only information necessary should be the
        bitrate; all other configuration information for the ReportData
        instances should be specified as part of this function, and should be
        considered to be characteristic of this subclass definition.

        A good operating definition of this prototypical empty class is that
        it defines unionability.

        EXAMPLE:
        --------

        @classmethod
        def __report_data_prototype__(cls, bitrate=__default_bitrate__)
            data = {
                'histogram': Histogram(bitrate=bitrate),
                'statistics': Statistics(bitrate=bitrate)
            }
        """

    @staticmethod
    @abc.abstractmethod
    def is_anomalous(timeseries):
        """
        MUST BE A STATICMETHOD.

        Define a method for testing whether a timeseries is anomalous. If so,
        the report generated from this timeseries will be unioned into
        report_anomalies_only. If not, the report generated from this
        timeseries will be unioned into report_sans_anomalies. In any case,
        the report will be unioned into report, which contains report data on
        the entire timeseries contained in the ReportSet.
        """

    def fold_in_timeseries(self, timeseries, time_intervals,
                           bitrate=__default_bitrate__):
        """
        Return a new report containing the current report's data along with
        data gleaned from the timeseries provided as an argument folded in.
        """
        return self.union(type(self).from_timeseries(
            timeseries, time_intervals, bitrate))

    def __union__(self, other):
        ans = self.clone()
        ans.time_intervals  += other.time_intervals
        for key in ans._data:
            ans._data[key] += other._data[key]
        return ans

    def __clone__(self):
        cloned_data = self._data
        for key in cloned_data:
            cloned_data[key] = cloned_data[key].clone()
        return type(self)(
            bitrate         = self.bitrate,
            version         = self.version,
            time_intervals  = self.time_intervals.clone(),
            data            = cloned_data
        )

    def _confirm_unionability(self, other):
        if self.bitrate != other.bitrate:
            raise ValueError('Reports have different bitrates')
        if self.__version__ != other.__version__:
            raise ValueError('Reports have different versions')
        if not isinstance(self, type(other)):
            raise ValueError('Type mismatch: cannot union ' +
                             str(type(self)) + ' with ' + str(type(other)))
        if set(self._data) != set(other._data):
            raise ValueError(
                'AbstractReportData sets do not have matching key sets.')
        if self.time_intervals.intersection(
                other.time_intervals) != TimeIntervalSet():
            raise ValueError('Reports have overlapping time intervals.')
        return True

    # TODO confirm self data unionability with new class instance
    def _assert_self_consistent(self):
        """
        Confirm that this Report is self-consistent. It should not generally
        be necessary to modify this, except perhaps to extend it in subclasses.
        """
        for key in self._data:
            if not isinstance(self._data[key], AbstractReportData):
                raise ValueError(
                    'key ' +
                    str(key) +
                    ' must be instance of AbstractReportData')
            self._data[key]._assert_self_consistent()
            if self.bitrate != self._data[key].bitrate:
                raise ValueError('Report constituents have different bitrates')
            if self.__version__ != self._data[key].__version__:
                raise ValueError('Report constituents have different versions')
        if not isinstance(self.time_intervals, TimeIntervalSet):
            raise ValueError(
                'self.time_intervals must be an instance of TimeIntervalSet.')
        if self.__version__ != self.time_intervals.__version__:
            raise ValueError(
                'time_intervals has different version than the Report itself')
        assert np.int64(
            self.bitrate) == self.bitrate, 'bitrate must be an integer'

    @classmethod
    def __from_dict__(cls, d):
        data = dict()
        data_dict = d['data']
        for key in data_dict:
            # for each ReportData dict, confirm it is a subclass and then
            # initialize from dictionary. note that THIS ONLY WORKS FOR
            # CLASSES DECLARED WITHIN THIS DOCUMENT due to lexical scoping.
            # an alternative implementation could be used in the future if
            # it ever became important to allow multiple source files or
            # interactive prototyping.
            report_data_class = globals()[ data_dict[key]['class'] ]
            if not issubclass(report_data_class, AbstractReportData):
                raise ValueError('Cannot reconstruct Report data; class '
                                 'property not a valid AbstractReportData '
                                 'subclass')
            data[key] = report_data_class.__from_dict__(data_dict[key])
        return cls(
            bitrate         = d['bitrate'],
            version         = d['version'],
            time_intervals  = TimeIntervalSet.__from_dict__(
                d['time_intervals']),
            data            = data
        )

    def __to_dict__(self):
        data = dict()
        for key in self._data:
            data[key] = self._data[key].__to_dict__()
        return {
            'bitrate':          self.bitrate,
            'version':          self.__version__,
            'time_intervals':   self.time_intervals.__to_dict__(),
            'data':             data
        }

    def __eq__(self, other):
        if not isinstance(self, type(other)) or set(
                self._data) != set(other._data):
            return False
        if (self.bitrate != other.bitrate or
                self.__version__ != other.__version__):
            return False
        if self.time_intervals != other.time_intervals:
            return False
        for key in self._data:
            if self._data[key] != other._data[key]:
                return False
        return True


class IRIGBReport(AbstractReport):

    def __init__(self):
        # TODO: Implement
        raise NotImplementedError()

    def is_anomalous(timeseries):
        # For now, always assume non-anomalous
        return False


class DuoToneReport(AbstractReport):

    def __init__(self):
        # TODO: Implement
        raise NotImplementedError()

    def is_anomalous(timeseries):
        # For now, always assume non-anomalous
        return False


class ReportSet(ReportInterface):
    """
    Class for collections of Reports, allowing for more advanced procedures
    that allow the user to distinguish between anomalous and typical time
    ranges in the input data.
    """

    # TODO Add notes, full intended time, current work block, and is_finished
    # method
    def __init__(self,
                 report_class_name,
                 bitrate                 = __default_bitrate__,
                 version                 = __version__,
                 channel_name            = "blank_report",
                 time_intervals          = None,
                 report                  = None,
                 report_anomalies_only   = None,
                 report_sans_anomalies   = None,
                 missing_times           = None):
        if version != self.__version__:
            raise VersionException()

        if isinstance(report_class_name, str):
            self.report_class_name = report_class_name
            if not self.get_report_class() is type:
                raise ValueError('report_class must be equal to the name of '
                                 'a ReportData class')
        else:
            raise ValueError('report_class must be a string')

        if time_intervals is None:
            self.time_intervals         = TimeIntervalSet()
        else:
            self.time_intervals         = time_intervals.clone()

        if missing_times is None:
            self.missing_times          = TimeIntervalSet()
        else:
            self.missing_times          = missing_times.clone()

        # All or none of the three reports must be provided as arguments,
        # otherwise it would be possible to initialize an inconsistent
        # ReportSet.
        if (report is None and
                report_anomalies_only is None and
                report_sans_anomalies is None):
            self.report                 = \
                self.get_report_class()(bitrate=bitrate)
            self.report_anomalies_only  = \
                self.get_report_class()(bitrate=bitrate)
            self.report_sans_anomalies  = \
                self.get_report_class()(bitrate=bitrate)
        else:
            self.report                 = report.clone()
            self.report_anomalies_only  = report_anomalies_only.clone()
            self.report_sans_anomalies  = report_sans_anomalies.clone()

        assert np.int64(bitrate) == bitrate, 'bitrate must be an integer'
        self.bitrate                = np.int64(bitrate)
        self.channel_name           = channel_name

        self._assert_self_consistent()

    def get_report_class(self):
        """
        Get the specific class of report used in this report set.

        If the function is called from ReportSet, the user must provide the
        self argument, which is then either interpreted as an instance of
        ReportSet, or as the class name string itself. In the latter case,
        this function simply returns the Report class corresponding to the
        class name passed as an argument.
        """
        if not isinstance(self, str):
            self = self.report_class_name
        return globals()[self]

    @staticmethod
    def from_time_and_channel_name(report_class_name, channel_name,
                                   time_intervals, bitrate=__default_bitrate__):
        """
        Each subclass of ReportSet should have its own well-defined
        constructor that rejects initialization data that would lead to an
        instance un-unionable with a new blank instance of that subclass.

        This can be confirmed by checking at the end of initialization that the
        new instance is unionable with a new blank instance.

        The time_intervals argument must, at the moment, correspond to a single
        gravitational wave frame file. Future implementations might change this.
        """
        report_class = globals()[report_class_name]
        try:
            timeseries = Timeseries.from_time_and_channel_name(
                channel_name, time_intervals)
            missing_times = TimeIntervalSet()
            # FIXME: This line is broken. This is a staticmethod, no self.
            report = report_class.from_timeseries(self, timeseries)

            if report_class.is_anomalous(timeseries):
                report_anomalies_only = report
                report_sans_anomalies = report_class(
                    bitrate=bitrate, time_intervals=time_intervals)
            else:
                report_sans_anomalies = report
                report_anomalies_only = report_class(
                    bitrate=bitrate, time_intervals=time_intervals)
        except MissingChannelDataException:
            missing_times = time_intervals
            report = report_class(
                bitrate=bitrate,
                time_intervals=time_intervals)
            report_anomalies_only = report
            report_sans_anomalies = report

        # FIXME: This line is ALSO broken. This is a staticmethod, no cls.
        return cls(
            report_class_name       = report_class_name,
            bitrate                 = bitrate,
            channel_name            = channel_name,
            time_intervals          = time_intervals,
            report                  = report,
            report_sans_anomalies   = report_sans_anomalies,
            report_anomalies_only   = report_anomalies_only,
            missing_times           = missing_times
        )

    def _assert_self_consistent(self):
        # TODO: make sure the r.__name__ business below works
        for r in (self.report, self.report_anomalies_only,
                  self.report_sans_anomalies):
            if not isinstance(r, self.get_report_class()):
                raise ValueError(
                    'key ' +
                    r.__name__ +
                    ' must be instance of ' +
                    self.report_class_name)
            r._assert_self_consistent()
            # r._confirm_unionability(self.get_report_class()(self.bitrate))
            if self.bitrate != r.bitrate:
                raise ValueError(
                    'key ' +
                    r.__name__ +
                    ' has different bitrate than this ReportSet')
            if self.__version__ != r.__version__:
                raise ValueError(
                    'key ' +
                    r.__name__ +
                    ' has different version than this ReportSet')
        for t in self.time_intervals, self.missing_times:
            if not isinstance(t, TimeIntervalSet):
                raise ValueError(
                    'key ' +
                    t.__name__ +
                    ' must be instance of TimeIntervalSet')
            t._assert_self_consistent()
            if self.__version__ != t.__version__:
                raise ValueError(
                    'key ' +
                    t.__name__ +
                    ' has different version than this ReportSet')
        if (self.report_anomalies_only + self.report_sans_anomalies !=
                self.report):
            raise ValueError(
                'whole report should be union of anomalous and nominal parts')
        if self.missing_times + self.time_intervals != self.time_intervals:
            raise ValueError(
                'missing times should be subset of all times in ReportSet')
        if self.time_intervals != self.report.time_intervals:
            raise ValueError(
                'time intervals in full Report and ReportSet should match')
        assert np.int64(
            self.bitrate) == self.bitrate, 'bitrate must be an integer'

    def _confirm_unionability(self, other):
        if not isinstance(self, type(other)):
            raise ValueError('instances of ReportSet must be of same type')
        if self.get_report_class() != other.get_report_class():
            raise ValueError(
                'instances of ReportSet must have same Report class')
        if self.channel_name != other.channel_name:
            raise ValueError(
                'instances of ReportSet must have same channel_name')
        if self.bitrate != other.bitrate:
            raise ValueError('instances of ReportSet must have same bitrate')
        if self.__version__ != other.__version__:
            raise ValueError('instances of ReportSet must have same version')
        if self.time_intervals.intersection(
                other.time_intervals) == TimeIntervalSet([]):
            raise ValueError('instances of ReportSet cannot cover overlapping '
                             'time intervals')

    def __union__(self, other):
        ans = self.clone()
        ans.time_intervals          += other.time_intervals
        ans.missing_times           += other.missing_times
        ans.report                  += other.report
        ans.report_anomalies_only   += other.report_anomalies_only
        ans.report_sans_anomalies   += other.report_sans_anomalies

    def __clone__(self):
        return type(self)(
            report_class_name       = self.report_class_name,
            bitrate                 = self.bitrate,
            version                 = self.__version__,
            channel_name            = self.channel_name,
            time_intervals          = self.time_intervals,
            report                  = self.report,
            report_anomalies_only   = self.report_anomalies_only,
            report_sans_anomalies   = self.report_sans_anomalies,
            missing_times           = self.missing_times
        )

    @classmethod
    def __from_dict__(cls, d):
        return cls(
            report_class_name       = d['report_class_name'],
            bitrate                 = d['bitrate'],
            version                 = d['version'],
            channel_name            = d['channel_name'],
            time_intervals          = TimeIntervalSet.__from_dict__(
                d['time_intervals']),
            report                  = cls.get_report_class(
                d['report_class_name']).__from_dict__(d['report']),
            report_anomalies_only   = cls.get_report_class(
                d['report_class_name']).__from_dict__(
                d['report_anomalies_only']),
            report_sans_anomalies   = cls.get_report_class(
                d['report_class_name']).__from_dict__(
                d['report_sans_anomalies']),
            missing_times           = TimeIntervalSet.__from_dict__(
                d['missing_times'])
        )

    def __to_dict__(self):
        return {
            'report_class_name':      self.report_class_name,
            'bitrate':                np.int64(self.bitrate),
            'version':                self.__version__,
            'channel_name':           self.channel_name,
            'time_intervals':         self.time_intervals.__to_dict__(),
            'report':                 self.report.__to_dict__(),
            'report_anomalies_only':  self.report_anomalies_only.__to_dict__(),
            'report_sans_anomalies':  self.report_sans_anomalies.__to_dict__(),
            'missing_times':          self.missing_times.__to_dict__()
        }

    def __eq__(self, other):
        try:
            self._assert_self_consistent()
            other._assert_self_consistent()
        except ValueError():
            return False
        if not isinstance(self, type(other)):
            return False
        if self.report_class_name != other.report_class_name:
            return False
        if self.bitrate != other.bitrate:
            return False
        if self.__version__ != other.__version__:
            return False
        if self.channel_name != other.channel_name:
            return False
        if self.time_intervals != other.time_intervals:
            return False
        if self.missing_times != other.missing_times:
            return False
        if self.report != other.report:
            return False
        if self.report_anomalies_only != other.report_anomalies_only:
            return False
        if self.report_sans_anomalies != other.report_sans_anomalies:
            return False
        return True

# TODO: Move tests to a separate directory


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
    ReportInterface.__save_dict_to_hdf5__(
        ex, 'geco_statistics_test_hdf5_dict_example.hdf5')
    loaded = ReportInterface.__load_dict_from_hdf5__(
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

