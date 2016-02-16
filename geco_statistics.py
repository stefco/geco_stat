import sys
import bisect
import os
import subprocess
import datetime
import h5py
import abc
import numpy as np

VERSION = '0.0.8'
DEFAULT_BITRATE = 16384

# could use the interval package, but would be one more external dependency
# TODO: implement the new __union__ and __clone__ impl. detail methods
class VersionError(Exception):
    """
    For when the user attempts to instantiate an object using a
    datastructure from a different version number of the class.
    """

class ReportInterface(object):
    "Abstract interface used by all geco_statistics classes"
    __metaclass__  = abc.ABCMeta
    _version = VERSION

    def union(self, other):
        "Aggregate these two instances. Must be of compatible type."
        self._confirm_self_consistency()
        other._confirm_self_consistency()
        self._confirm_compatibility(other)
        return self.__union__(other)

    def clone(self):
        "Create a new object that is an exact copy of this instance."
        self._confirm_self_consistency()
        return self.__clone__()

    @abc.abstractmethod
    def __to_dict__(self):
        """
        Return a dictionary whose elements consist of strings, ints, lists, or
        numpy.ndarray objects, or of other dicts whose contents follow this
        pattern recursively. This dictionary must wholly represent the data in
        this object, so that this object may be totally reconstructed using
        the dictionary's contents. This is an implementation method used to
        store data in HDF5.
        """

    @abc.abstractmethod
    def __from_dict__(cls, dict):
        """
        Construct an instance of this class using a dictionary of the form output
        by self.__to_dict__. Should generally be a class method.
        """

    @abc.abstractmethod
    def __clone__(self):
        """
        Create a new object that is an exact copy of this instance without
        first checking for self-consistency. This is part of the implementation
        of the clone method.
        """

    @abc.abstractmethod
    def __union__(self, other):
        """
        Aggregate these two instances without first checking that the instances
        are compatible or self-consistent. This is part of the implementation
        of the union method.
        """

    @abc.abstractmethod
    def _confirm_compatibility(self, other):
        "Make sure these two instances can be unioned."

    @abc.abstractmethod
    def _confirm_self_consistency(self):
        "Make sure this instance is self-consistent."

    @abc.abstractmethod
    def __eq__(self, other):
        "Instances must have a way of determining equality."

    def __ne__(self, other):
        return not self == other

    def __add__(self, other):
        'Addition can be used as a shorthand for union.'
        return type(self).union(self, other)

class Plottable(ReportInterface):
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
        Create some sort of verbose, human-readable text summary for the information
        content of this object. Should return a string.
        """

# TODO: Make Plottable
class TimeIntervalSet(ReportInterface):
    """
    TimeIntervalSet

    A class for storing sets of half open intervals of the form

        [t1,t2) U [t3,t4) U...

    along with methods for manipulating time interval sets, including

    - union(otherIntervalSet)
    - intersection(otherIntervalSet)
    - complement_with_respect_to(otherIntervalSet)
    - no_overlap_union(otherIntervalSet)

    These methods do not modify the TimeIntervalSet instance to which they are
    bound. This makes it easy to play around with them without annoying and
    potentially dangerous side-effects.
    """

    def __init__(self, intervalSet=None, start=None, end=None, version=VERSION):
        """
        If no time interval is given at initialization, the TimeIntervalSet
        begins empty. There are two ways to initialize it with a nonempty set
        of time intervals:

        1)  Provide an ordered numeric list (float, int, or mixed type are
            all fine) with even length as the intervalSet argument. The
            lists elements

            [s1, e1, s2, e2, ... sN, eN]

            are interpreted as forming the interval union

            [s1, e1) U [s2, e2) U ... U [sN, eN]

        2)  Provide numerical start and end values, start=s, end=e,
            corresponding to the beginning and end of a single interval
            that will comprise the new interval set:

            [s, e)
        """
        if version != self._version:
            raise VersionError()
        if type(intervalSet) == list or type(intervalSet) == np.ndarray:
            if len(intervalSet) % 2 != 0:
                raise ValueError('intervalSet set must have even length (equal starts and ends)')
            elif not np.array_equal(sorted(intervalSet), intervalSet):
                raise ValueError('intervalSet must be sorted')
            else:
                self._data = np.array([float(x) for x in intervalSet])
                self.remove_empty_sets()
                self._confirm_self_consistency()
        elif intervalSet == start == end == None or start == end:
            self._data = np.array([])
        elif start < end:
            self._data = np.array([float(start), float(end)])
            self.remove_empty_sets()
            self._confirm_self_consistency()
        else:
            raise ValueError('Invalid combination of arguments. See documentation.')

    def __union__(self, other):
        """
        Return the union of the current set of intervals with some other set.

        Returns a new TimeIntervalSet instance without modifying the input
        arguments.
        """
        if len(other) == 0:
            return self.clone()
        elif len(self) == 0:
            return other.clone()
        # iteratively union every interval in the other set into this set
        result = self.clone()
        for i in range(0, len(other)/2):
            # this part is (mostly)  shared between set algebra methods
            start  = other._data[2*i]
            end    = other._data[2*i + 1]
            bounds = result.__left_and_right_bounds__(start, end)
            left   = bounds[0] % 2
            right  = bounds[1] % 2
            # the conditional responses are unique to each set algebra method
            if left == 0 and right == 1:
                result._data = np.concatenate((result._data, result._data[0:bounds[0]], [start, end], result._data[bounds[1]+1:]))
            elif left == 0 and right == 0:
                result._data = np.concatenate((result._data, result._data[0:bounds[0]], [start], result._data[bounds[1]+1:]))
            elif left == 1 and right == 1:
                result._data = np.concatenate((result._data, result._data[0:bounds[0]], [end], result._data[bounds[1]+1:]))
            elif left == 1 and right == 0:
                result._data = np.concatenate((result._data, result._data[0:bounds[0]], result._data[bounds[1]+1:]))
            result.remove_empty_sets()
        return result

    def intersection(self, other):
        """
        Return the intersection of the current set of intervals with some other
        set.

        Returns a new TimeIntervalSet instance without modifying the input
        arguments.
        """
        self._confirm_self_consistency()
        other._confirm_self_consistency()
        if len(other) == 0 or len(self) == 0:
            return TimeIntervalSet()
        result = TimeIntervalSet()
        for i in range(0, len(other)/2):
            # this part is (mostly)  shared between set algebra methods
            start  = other._data[2*i]
            end    = other._data[2*i + 1]
            bounds = self.__left_and_right_bounds__(start, end) # this differs
            left   = bounds[0] % 2
            right  = bounds[1] % 2
            # the conditional responses are unique to each set algebra method
            if left == 0 and right == 1:
                result._data = np.concatenate((result._data, self._data[bounds[0]:bounds[1]+1]))
            elif left == 0 and right == 0:
                result._data = np.concatenate((result._data, self._data[bounds[0]:bounds[1]+1], [end]))
            elif left == 1 and right == 1:
                result._data = np.concatenate((result._data, [start], self._data[bounds[0]:bounds[1]+1]))
            elif left == 1 and right == 0:
                result._data = np.concatenate((result._data, [start], self._data[bounds[0]:bounds[1]+1], [end]))
            result.remove_empty_sets()
        return result

    def complement_with_respect_to(self, other):
        """
        Return the complement of the current set of intervals with respect to
        another set. The other set must be a superset of the current set, or
        else an error will be raised.

        Returns a new TimeIntervalSet instance without modifying the input
        arguments.
        """
        self._confirm_self_consistency()
        other._confirm_self_consistency()
        if self.union(other) != other:
            raise ValueError('Can only take complement with respect to a superset.')
        if len(self) == 0:
            return other
        result = TimeIntervalSet()
        for i in range(0, len(other)/2):
            # this part is (mostly)  shared between set algebra methods
            start  = other._data[2*i]
            end    = other._data[2*i + 1]
            bounds = self.__left_and_right_bounds__(start, end) # this differs
            left   = bounds[0] % 2
            right  = bounds[1] % 2
            # the conditional responses are unique to each set algebra method
            if left == 0 and right == 1:
                result._data = np.concatenate((result._data, [start], self._data[bounds[0]:bounds[1]+1], [end]))
            elif left == 0 and right == 0:
                result._data = np.concatenate((result._data, [start], self._data[bounds[0]:bounds[1]+1]))
            elif left == 1 and right == 1:
                result._data = np.concatenate((result._data, self._data[bounds[0]:bounds[1]+1], [end]))
            elif left == 1 and right == 0:
                result._data = np.concatenate((result._data, self._data[bounds[0]:bounds[1]+1]))
            result.remove_empty_sets()
        return result

    def __left_and_right_bounds__(self, a, b):
        """
        Used when merging an individual interval [a, b) into an existing
        TimeIntervalSet S. S must, implicitly, be sorted, of even length, and
        contain numerical data.

        This function returns a list L of length 2, such that:
        
            L[0] = index of leftmost value in S greater than or equal to a
            L[1] = index of rightmost value in S less than or equal to a

        L is then used to determine a merge strategy for the union, intersection,
        or complement of S with respect to [a, b).

        For the sake of simplicity of implementation, this function only accepts
        positive even length lists of start and end points. In other words, an
        error will be raised if the user tries passing an empty TimeIntervalSet.
        """
        if len(self._data) == 0:
            raise ValueError('Cannot use an empty TimeIntervalSet.')
        l = bisect.bisect_left(self._data, a)
        r = bisect.bisect_right(self._data, b) - 1
        return [l, r]

    def remove_empty_sets(self):
        """
        Find repeated endpoints and remove them pairwise. For example, the
        set

            [a, b) U [b, c)

        can be written

            [a, c)

        and the set

            [b, b)

        is empty, and can simply be removed.
        """
        self._confirm_self_consistency() # check
        i = 0
        while i < len(self._data) - 1:
            if self._data[i] == self._data[i+1]:
                self._data = np.delete(self._data, np.s_[i:i+2])
            else:
                i += 1           # not a copy, move on to the next one

    def _confirm_compatibility(self, other):
        self._confirm_self_consistency()
        other._confirm_self_consistency()
        if type(self) != type(other):
            raise ValueError('Type mismatch: cannot union ' + str(type(self)) + ' with ' + str(type(other)))
        if self._version != other._version:
            raise ValueError('TimeIntervalSets have different versions')
        return True

    def _confirm_self_consistency(self):
        'Check that this instance has form consistent with the class spec'
        if type(self._data) != np.ndarray:
            raise Exception('TimeIntervalSet corrupted: data not a numpy.ndarray')
        elif not np.array_equal(sorted(self._data), self._data):
            raise Exception('TimeIntervalSet corrupted: data not sorted')
        elif len(self._data) % 2 != 0:
            raise Exception('TimeIntervalSet corrupted: odd number of endpoints')
        return True

    def __clone__(self):
        return type(self)(self._data)

    def combined_length(self):
        'Get the combined length of all time intervals in this TimeIntervalSet.'
        if len(self._data) == 0:
            return 0
        starts = self._data[0::2]
        ends   = self._data[1::2]
        length = 0
        for i in range(0, len(starts)):
            length += ends[i] - starts[i]
        return length

    def human_readable_dates(self):
        """
        Print the contained time intervals in an immediately human-readable
        form, assuming that the time endpoints that comprise this instance
        are GPS times. For example,

            [1135825217, 1135825219) U [1135825220, 1135825222)

        will be printed in the more comprehensible form:

            [Sun Jan 03 03:00:00 GMT 2016, Sun Jan 03 03:00:02 GMT 2016) U
            [Sun Jan 03 03:00:03 GMT 2016, Sun Jan 03 03:00:05 GMT 2016)

        """
        times = [str(int(x)) for x in self._data]
        self._confirm_self_consistency()
        tstring = ""
        i = 0
        for time in times:
            dump = subprocess.Popen(["lalapps_tconvert",time], stdout=subprocess.PIPE)
            if i == 0:
                tstring += '[' + dump.communicate()[0][:-1] + ', '
                i = 1
            else:
                tstring += dump.communicate()[0][:-1] + ') U\n'
                i = 0
        tstring = tstring[:-3] # shave off the last U character and newline
        return tstring

    @classmethod
    def __from_dict__(cls, dict):
        return cls(dict['data'], version=dict['version'])

    def __to_dict__(self):
        return {'data': self._data, 'version': self._version}

    def __eq__(self, other):
        return np.array_equal(self._data, other._data)

    def __len__(self):
        return len(self._data)

    def __mul__(self, other):
        'Multiplication can be used as a shorthand for intersection.'
        return type(self).intersection(self, other)

    def __sub__(self, other):
        """
        Subtraction can be used as a shorthand for complement. Specifically:

            a - b = b.complement_with_respect_to(a)

        Take careful note that the order of operations is switched in order
        for the notation to make sense. With this convention, it is easy to
        see that

            (a - b) + b = a - (b - b) = a - b + b = a

        so that it is manifestly associative, though it is non-commutative
        and doesn't obey proper group behavior since e.g. (-a) is not
        defined.
        """
        return type(self).complement_with_respect_to(other, self)

    def __str__(self):
        'Return a string expressing the object in set union notation'
        self._confirm_self_consistency()
        if len(self) == 0:
            return '{}'
        starts = self._data[0::2]
        ends   = self._data[1::2]
        string = '[' + str(starts[0]) + ', ' + str(ends[0]) + ')'
        for i in range(1, len(starts)):
            string += ' U [' + str(starts[i]) + ', ' + str(ends[i]) + ')'
        return string

    def __repr__(self):
        self._confirm_self_consistency()
        return 'geco_statistics.TimeIntervalSet(' + repr(list(self._data)) + ')'

# TODO: Make Plottable
class ReportData(ReportInterface):
    "Abstract class for aggregated data. All instances must implement interface."
    __metaclass__  = abc.ABCMeta

    def from_timeseries(self, timeseries):
        """
        Create a ReportData object using timeseries data as input. This is
        an instance method, meant to create a new object compatible with
        the current instance; this approach allows for a trivially
        simple method interface, requiring only the timeseries array itself
        as input.

        The timeseries argument can be composed of multiple rows, representing
        multiple seconds, worth of data. It can also simply consist of an
        integer number of seconds worth of data. Consequently, the length of
        the (flattened) input timeseries must be an integer multiple of the
        bitrate.
        """
        timeseries = np.array(timeseries)
        l = len(timeseries.flatten())
        if l % self.bitrate != 0:
            raise ValueError('Flattened timeseries length must be integer mult of bitrate.')
        if l == 0:
            raise ValueError('Cannot pass an empty timeseries.')
        ans = self.__from_single_second_timeseries__(timeseries)
        for i in np.arange(1, l/bitrate):
            ans += self.__from_single_second_timeseries__(timeseries)
        return ans

    @abc.abstractmethod
    def __from_single_second_timeseries__(self, timeseries):
        """
        Return an instance of this class initiated using only a single second
        of timeseries data as input. The timeseries used must therefore have
        length equal to the bitrate. THIS MAY BE ASSUMED BY THE METHOD.
        """

# TODO: Make Plottable
class Histogram(ReportData):
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
            bitrate         = DEFAULT_BITRATE,
            version         = VERSION):
        """
        Initialize an instance of the class. All properties have default
        values corresponding to an empty statistics set; they can be
        individually overridden.
        """
        # make sure hist_range is an ordered pair of numbers
        if not len(hist_range) == 2:
            raise ValueError('second argument (hist_range) must have length 2')
        if version != self._version:
            raise VersionError()
        elif hist_range[0] >= hist_range[1]:
            raise ValueError('minimum value of histogram bin range must be smaller than max')

        # set values to "empty" histograms
        if hist == None:
            hist = np.zeros((hist_num_bins, bitrate), dtype=np.int64)

        self.hist_num_bins  = hist_num_bins
        self.hist_range     = hist_range
        self.hist           = hist
        self.hist_bins      = np.linspace(hist_range[0], hist_range[1], hist_num_bins+1)
        self._t_ticks       = np.linspace(0,1,16384,endpoint=False)
        self.bitrate        = bitrate

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

    def _confirm_compatibility(self, other):
        self._confirm_self_consistency()
        other._confirm_self_consistency()
        if self.hist_range != other.hist_range or self.hist_num_bins != other.hist_num_bins:
            raise ValueError('Histograms have different bin edges')
        if self.bitrate != other.bitrate:
            raise ValueError('Histograms have different bitrates')
        if self._version != other._version:
            raise ValueError('Histograms have different versions')
        if type(self) != type(other):
            raise ValueError('Type mismatch: cannot union ' + str(type(self)) + ' with ' + str(type(other)))
        return True
        
    def _confirm_self_consistency(self):
        if self._version != VERSION:
            raise ValueError('Histogram version ' + self._version + ' does not match lib version')
        return True

    @classmethod
    def __from_dict__(cls, dict):
        # TODO
        raise NotImplementedError()

    def __to_dict__(self):
        # TODO
        raise NotImplementedError()

    def __eq__(self, other):
        try:
            self._confirm_compatibility(other)
        except ValueError:
            return False
        return np.array_equal(self.hist, other.hist)

# TODO: Make Plottable
class Statistics(ReportData):
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
            max             = np.iinfo(np.int64).min, # lowest possible max, cannot survive
            min             = np.iinfo(np.int64).max, # same for min
            num             = 0,
            bitrate         = DEFAULT_BITRATE,
            version         = VERSION):
        """
        All properties have default values corresponding to an empty statistics
        set; they can be individually overridden.
        """
        if version != self._version:
            raise VersionError()
        # set values of sum, sum_sq, and the histograms, since these depend on
        # bitrate and hist_num_bins and hence cannot be set above
        if sum          == None: sum         = np.zeros(bitrate)
        if sum_sq       == None: sum_sq      = np.zeros(bitrate)

        self.sum        = sum
        self.sum_sq     = sum_sq
        self.max        = max
        self.min        = min
        self.num        = num
        self.bitrate    = bitrate

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
        self._confirm_self_consistency()
        return type(self)(
            sum             = self.sum,
            sum_sq          = self.sum_sq,
            max             = self.max,
            min             = self.min,
            num             = self.num,
            bitrate         = self.bitrate
        )

    def _confirm_compatibility(self, other):
        self._confirm_self_consistency()
        other._confirm_self_consistency()
        if self.bitrate != other.bitrate:
            raise ValueError('Statistics have different bitrates')
        if self._version != other._version:
            raise ValueError('Statistics have different versions')
        if type(self) != type(other):
            raise ValueError('Type mismatch: cannot union ' + str(type(self)) + ' with ' + str(type(other)))
        return True

    def _confirm_self_consistency(self):
        if self._version != VERSION:
            raise ValueError('Statistics version ' + self._version + ' does not match lib version')
        return True

    @classmethod
    def __from_dict__(cls, dict):
        # TODO
        raise NotImplementedError()

    def __to_dict__(self):
        # TODO
        raise NotImplementedError()

    def __eq__(self, other):
        try:
            self._confirm_compatibility(other)
        except ValueError:
            return False
        return (
            np.array_equal(self.sum,    other.sum)      and
            np.array_equal(self.sum_sq, other.sum_sq)   and
            np.array_equal(self.max,    other.max)      and
            np.array_equal(self.min,    other.min)      and
            np.array_equal(self.num,    other.num)
        )

# TODO: Make Plottable
class Report(ReportInterface):
    """
    A class for generating reports on data integrity. Should be extended to
    create reports specific to different types of data, e.g. IRIGBReport
    and DuoToneReport.

    The Report class contains information on the time intervals included
    as well as basic statistics (mean, max, min, standard deviation)
    on the time intervals included, and finally, multiple histograms
    covering multiple "zoom" levels, for a tailored view of the data.
    """
    def __init__(self,
            bitrate         = DEFAULT_BITRATE,
            version         = VERSION,
            time_intervals  = TimeIntervalSet(),
            data            = None):

        if version != self._version:
            raise VersionError()

        if data == None:
            data = {
                'histogram': Histogram(bitrate=bitrate),
                'statistics': Statistics(bitrate=bitrate)
            }
        self.bitrate        = bitrate
        self.time_intervals = time_intervals
        self._data          = data              # data 'lives' here
        self.histogram      = data['histogram'] # pointers maintained for convenience
        self.statistics     = data['statistics']
        self._confirm_self_consistency()

    def fold_in_timeseries(self, timeseries, time_intervals, bitrate=DEFAULT_BITRATE):
        """
        Return a new report containing the current report's data along with
        data gleaned from the timeseries provided as an argument folded in.
        """
        return self.union(type(self).from_timeseries(timeseries, time_intervals, bitrate))

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

    def _confirm_compatibility(self, other):
        self._confirm_self_consistency()
        other._confirm_self_consistency()
        if self.bitrate != other.bitrate:
            raise ValueError('Reports have different bitrates')
        if self._version != other._version:
            raise ValueError('Reports have different versions')
        if type(self) != type(other):
            raise ValueError('Type mismatch: cannot union ' + str(type(self)) + ' with ' + str(type(other)))
        if set(self._data) != set(other._data):
            raise ValueError('ReportData sets do not have matching key sets.')
        if self.time_intervals.intersection(other.time_intervals) != TimeIntervalSet():
            raise ValueError('Reports have overlapping time intervals.')
        return True

    def _confirm_self_consistency(self):
        """
        Confirm that this Report is self-consistent. It should not generally
        be necessary to modify this, except perhaps to extend it in subclasses.
        """
        for key in self._data:
            if not isinstance(self._data[key], ReportData):
                raise ValueError('key ' + str(key) + ' must be instance of ReportData')
            if self.bitrate != self._data[key].bitrate:
                raise ValueError('Report constituents have different bitrates')
            if not (self._version == self.time_intervals._version == self._data[key]._version):
                raise ValueError('Report constituents have different versions')
        if self._version != VERSION:
            raise ValueError('Report version ' + self._version + ' does not match lib version')
        if not isinstance(self.time_intervals, TimeIntervalSet):
            raise ValueError('self.time_intervals must be an instance of TimeIntervalSet.')

    def __add__(self, other):
        return type(self).union(self, other)

# TODO: DT and IRIG report classes; everything should fit into a report;
# TODO: Add ReportSet class and some trivial subclasses. These determine anomalousness.
# a report contains both statistics and histogram classes.

class ReportSet(ReportInterface):
    """
    Abstract class for collections of Reports, allowing for more advanced procedures
    that allow the user to distinguish between anomalous and typical time ranges in
    the input data."
    """

    def __init__(self,
            bitrate                 = DEFAULT_BITRATE,
            version                 = VERSION,
            time_intervals          = TimeIntervalSet(),
            report                  = None,
            report_anomalies_only   = None,
            report_sans_anomalies   = None,
            missing_times           = TimeIntervalSet()):
        "Initialize a new ReportSet. This should be customized in subclasses."
        if version != self._version:
            raise VersionError()

        # TODO:
        raise NotImplementedError()

    @classmethod
    @abc.abstractmethod
    def anomaly_test(cls, timeseries):
        "Define a method for testing whether a timeseries is anomalous."

    def save_hdf5(self, filename):
        """Save this instance to an hdf5 file."""
        # TODO
        raise NotImplementedError

    @classmethod
    def load_hdf5(cls, filename):
        """Load an instance saved in an hdf5 file."""
        # TODO:
        raise NotImplementedError()
