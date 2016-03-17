# -*- coding: utf-8 -*-

import numpy as np      # >=1.10.4
from geco_stat._version import __version__, __release__
from geco_stat._constants import __default_bitrate__
from geco_stat.Exceptions import MissingChannelDataException
from geco_stat.Abstract import Factory
from geco_stat.Abstract import AbstUnionable
from geco_stat.Abstract import AbstractPlottable
from geco_stat.Abstract import HDF5_IO
from geco_stat.Time import TimeIntervalSet

# Inherit from HDF5_IO first in order to get an implemented clone method
class ReportSet(HDF5_IO,
                # AbstractPlottable, TODO Make AbstractPlottable
                AbstUnionable):
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
                 channel_name            = "blank_report",
                 time_intervals          = None,
                 report                  = None,
                 report_anomalies_only   = None,
                 report_sans_anomalies   = None,
                 missing_times           = None):

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

        self.assert_self_consistent()

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

    def assert_self_consistent(self):
        # TODO: make sure the r.__name__ business below works
        for r in (self.report, self.report_anomalies_only,
                  self.report_sans_anomalies):
            if not isinstance(r, self.get_report_class()):
                raise ValueError(
                    'key ' +
                    r.__name__ +
                    ' must be instance of ' +
                    self.report_class_name)
            r.assert_self_consistent()
            # r.assert_unionable(self.get_report_class()(self.bitrate))
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
            t.assert_self_consistent()
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

    def assert_unionable(self, other):
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
            channel_name            = d['channel_name'],
            time_intervals          = TimeIntervalSet.from_dict(
                d['time_intervals']),
            report                  = cls.get_report_class(
                d['report_class_name']).from_dict(d['report']),
            report_anomalies_only   = cls.get_report_class(
                d['report_class_name']).from_dict(
                d['report_anomalies_only']),
            report_sans_anomalies   = cls.get_report_class(
                d['report_class_name']).from_dict(
                d['report_sans_anomalies']),
            missing_times           = TimeIntervalSet.from_dict(
                d['missing_times'])
        )

    def __to_dict__(self):
        return {
            'report_class_name':      self.report_class_name,
            'bitrate':                np.int64(self.bitrate),
            'channel_name':           self.channel_name,
            'time_intervals':         self.time_intervals.to_dict(),
            'report':                 self.report.to_dict(),
            'report_anomalies_only':  self.report_anomalies_only.to_dict(),
            'report_sans_anomalies':  self.report_sans_anomalies.to_dict(),
            'missing_times':          self.missing_times.to_dict()
        }

    def __eq__(self, other):
        try:
            self.assert_self_consistent()
            other.assert_self_consistent()
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

