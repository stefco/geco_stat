# -*- coding: utf-8 -*-

import abc
import numpy as np      # >=1.10.4
from geco_stat._version import __version__
from geco_stat._constants import __default_bitrate__
from geco_stat.Abstract import Factory
from geco_stat.Data import AbstData
from geco_stat.Time import TimeIntervalSet

# TODO: Make AbstractPlottable
class AbstReport(AbstData):
    """
    A class for generating reports on data integrity. Should be extended to
    create reports specific to different types of data, e.g. IRIGBReport
    and DuoToneReport.

    The AbstReport class contains information on the time intervals included
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
                 time_intervals  = None,
                 data            = None):

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
                raise ValueError('AbstData dictionary should not '
                                 'have attributes conflicting with '
                                 'AbstReport attributes.')
            setattr(self, key, data[key])
        self.assert_self_consistent()

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
            time_intervals  = self.time_intervals.clone(),
            data            = cloned_data
        )

    def assert_unionable(self, other):
        if self.bitrate != other.bitrate:
            raise ValueError('Reports have different bitrates')
        if self.__version__ != other.__version__:
            raise ValueError('Reports have different versions')
        if not isinstance(self, type(other)):
            raise ValueError('Type mismatch: cannot union ' +
                             str(type(self)) + ' with ' + str(type(other)))
        if set(self._data) != set(other._data):
            raise ValueError(
                'AbstData sets do not have matching key sets.')
        if self.time_intervals.intersection(
                other.time_intervals) != TimeIntervalSet():
            raise ValueError('Reports have overlapping time intervals.')
        return True

    # TODO confirm self data unionability with new class instance
    def assert_self_consistent(self):
        """
        Confirm that this Report is self-consistent. It should not generally
        be necessary to modify this, except perhaps to extend it in subclasses.
        """
        for key in self._data:
            if not isinstance(self._data[key], AbstData):
                raise ValueError(
                    'key ' +
                    str(key) +
                    ' must be instance of AbstData')
            self._data[key].assert_self_consistent()
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

    # FIXME this needs to be completely revamped to reflect a simpler structure
    # for Reports. It seems that subclassing AbstReport should mainly just
    # involve specifying the classes of ReportData that it uses.
    @classmethod
    def __from_dict__(cls, d):
        data = dict()
        for key, value in d['data'].items():
            # FIXME implement this using the Factory pattern used elsewhere.
            report_data_class = globals()[ value['class'] ]
            if not issubclass(report_data_class, AbstData):
                raise ValueError('Cannot reconstruct Report data; class '
                                 'property not a valid AbstData '
                                 'subclass')
            data[key] = report_data_class.from_dict(value)
        return cls(
            bitrate         = d['bitrate'],
            time_intervals  = TimeIntervalSet.from_dict(
                d['time_intervals']),
            data            = data
        )

    def __to_dict__(self):
        data = dict()
        for key in self._data:
            data[key] = self._data[key].to_dict()
        return {
            'bitrate':          self.bitrate,
            'time_intervals':   self.time_intervals.to_dict(),
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

class IRIGBReport(AbstReport):
    def __init__(self):
        # TODO: Implement
        raise NotImplementedError()

    def is_anomalous(timeseries):
        # For now, always assume non-anomalous
        return False


class DuoToneReport(AbstReport):
    def __init__(self):
        # TODO: Implement
        raise NotImplementedError()

    def is_anomalous(timeseries):
        # For now, always assume non-anomalous
        return False

Factory.add_class(IRIGBReport)
Factory.add_class(DuoToneReport)
