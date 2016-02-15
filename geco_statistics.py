import sys
import bisect
import os
import subprocess
import datetime
import h5py
import numpy as np

VERSION = '0.0.4'
DEFAULT_BITRATE = 16384

# could use the interval package, but would be one more external dependency
class TimeIntervalSet(object):
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

    def __init__(self, intervalSet=None, start=None, end=None):
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
        self._version = VERSION
        if type(intervalSet) == list:
            if len(intervalSet) % 2 != 0:
                raise ValueError('intervalSet set must have even length (equal starts and ends)')
            elif sorted(intervalSet) != intervalSet:
                raise ValueError('intervalSet must be sorted')
            else:
                self._data = [float(x) for x in intervalSet]
                self.remove_empty_sets()
                self._confirm_self_consistency()
        elif intervalSet == start == end == None or start == end:
            self._data = []
        elif start < end:
            self._data = [float(start), float(end)]
            self.remove_empty_sets()
            self._confirm_self_consistency()
        else:
            raise ValueError('Invalid combination of arguments. See documentation.')

    def union(self, other):
        """
        Return the union of the current set of intervals with some other set.

        Returns a new TimeIntervalSet instance without modifying the input
        arguments.
        """
        self._confirm_self_consistency()
        other._confirm_self_consistency()
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
                result._data = result._data[0:bounds[0]] + [start, end] + result._data[bounds[1]+1:]
            elif left == 0 and right == 0:
                result._data = result._data[0:bounds[0]] + [start] + result._data[bounds[1]+1:]
            elif left == 1 and right == 1:
                result._data = result._data[0:bounds[0]] + [end] + result._data[bounds[1]+1:]
            elif left == 1 and right == 0:
                result._data = result._data[0:bounds[0]] + result._data[bounds[1]+1:]
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
                result._data += self._data[bounds[0]:bounds[1]+1]
            elif left == 0 and right == 0:
                result._data += self._data[bounds[0]:bounds[1]+1] + [end]
            elif left == 1 and right == 1:
                result._data += [start] + self._data[bounds[0]:bounds[1]+1]
            elif left == 1 and right == 0:
                result._data += [start] + self._data[bounds[0]:bounds[1]+1] + [end]
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
                result._data += [start] + self._data[bounds[0]:bounds[1]+1] + [end]
            elif left == 0 and right == 0:
                result._data += [start] + self._data[bounds[0]:bounds[1]+1]
            elif left == 1 and right == 1:
                result._data += self._data[bounds[0]:bounds[1]+1] + [end]
            elif left == 1 and right == 0:
                result._data += self._data[bounds[0]:bounds[1]+1]
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
                self._data.pop(i) # remove this instance of the value...
                self._data.pop(i) # and the one to its right.
            else:
                i += 1           # not a copy, move on to the next one

    def _confirm_self_consistency(self):
        'Check that this instance has form consistent with the class spec'
        if type(self._data) != list:
            raise Exception('TimeIntervalSet corrupted: data not a list')
        elif sorted(self._data) != self._data:
            raise Exception('TimeIntervalSet corrupted: data not sorted')
        elif len(self._data) % 2 != 0:
            raise Exception('TimeIntervalSet corrupted: odd number of endpoints')
        return True

    def clone(self):
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
        # raise Exception('not yet defined')
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

    def __eq__(self, other):
        return self._data == other._data

    def __ne__(self, other):
        return self._data != other._data

    def __len__(self):
        return len(self._data)

    def __mul__(self, other):
        'Multiplication can be used as a shorthand for intersection.'
        return type(self).intersection(self, other)

    def __add__(self, other):
        'Addition can be used as a shorthand for union.'
        return type(self).union(self, other)

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
        if self.__len__() == 0:
            return '{}'
        starts = self._data[0::2]
        ends   = self._data[1::2]
        string = '[' + str(starts[0]) + ', ' + str(ends[0]) + ')'
        for i in range(1, len(starts)):
            string += ' U [' + str(starts[i]) + ', ' + str(ends[i]) + ')'
        return string

    def __repr__(self):
        self._confirm_self_consistency()
        return 'geco_statistics.TimeIntervalSet(' + repr(self._data) + ')'

class Histogram(object):
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
        elif hist_range[0] >= hist_range[1]:
            raise ValueError('minimum value of histogram bin range must be smaller than max')

        # set values to "empty" histograms
        if hist     == None: hist        = np.zeros((hist_num_bins, bitrate), dtype=np.int64),

        self.hist_num_bins  = hist_num_bins
        self.hist_range     = hist_range
        self.hist           = hist
        self.hist_bins      = np.linspace(hist_range[0], hist_range[1], hist_num_bins+1)
        self.bitrate        = bitrate
        self._version       = version

    @classmethod
    def from_timeseries(cls, timeseries, time_range, bitrate=DEFAULT_BITRATE):
        # TODO
        raise Exception('not yet implemented')

    def union(self, other):
        """
        Take the union of these two histograms, representing the histogram of
        the union of the two histograms' respective datasets.
        """
        self.is_compatible_with(other)
        ans         = self.clone()
        ans.hist    = self.hist + other.hist
        return ans

    def clone(self):
        self._confirm_self_consistency()
        return type(self)(
            hist            = self.hist,
            hist_range      = self.hist_range,
            hist_num_bins   = self.hist_num_bins,
            bitrate         = self.bitrate
        )

    def is_compatible_with(self, other):
        if self.hist_range != other.hist_range or self.hist_num_bins != other.hist_num_bins:
            raise ValueError('Histograms have different bin edges')
        if self.bitrate != other.bitrate:
            raise ValueError('Histograms have different bitrates')
        if self._version != VERSION:
            raise ValueError('Histogram version ' + self._version + ' does not match lib version')
        if self._version != other._version:
            raise ValueError('Histograms have different bitrates')
        if type(self) != type(other):
            raise ValueError('Type mismatch: cannot union ' + str(type(self)) + ' with ' + str(type(other)))
        return True
        
    def _confirm_self_consistency(self):
        if self._version != VERSION:
            raise ValueError('Histogram version ' + self._version + ' does not match lib version')
        return True

    def __eq__(self, other):
        try:
            self.is_compatible_with(other)
        except ValueError:
            return False
        return np.array_equal(self.hist, other.hist)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __add__(self, other):
        return type(self).union(self, other)

class Statistics(object):
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
            bitrate         = DEFAULT_BITRATE,
            version         = VERSION):
        """
        All properties have default values corresponding to an empty statistics
        set; they can be individually overridden.
        """
        # set values of sum, sum_sq, and the histograms, since these depend on
        # bitrate and hist_num_bins and hence cannot be set above
        if sum          == None: sum         = np.zeros(bitrate)
        if sum_sq       == None: sum_sq      = np.zeros(bitrate)

        self.sum        = sum
        self.sum_sq     = sum_sq
        self.max        = max
        self.min        = min
        self.bitrate    = bitrate
        self._version   = version

    @classmethod
    def from_timeseries(cls, timeseries, time_range, bitrate=DEFAULT_BITRATE):
        """
        Create a statistics object from timeseries data. The timeseries can be
        an integer multiple of the bitrate, in which case it is interpreted
        as comprising multiple seconds worth of data.
        """
        # TODO
        raise Exception('not yet implemented')

    def union(self, other):
        """
        Take the union of these statistics, representing the same statistics
        taken on the union of the two statistics objects' respective datasets.
        """
        self.is_compatible_with(other)
        ans         = self.clone()
        ans.sum     = self.sum      + other.sum
        ans.sum_sq  = self.sum_sq   + other.sum_sq
        ans.max     = self.max      + other.max
        ans.min     = self.min      + other.min
        return ans

    def clone(self):
        self._confirm_self_consistency()
        return type(self)(
            sum             = self.sum,
            sum_sq          = self.sum_sq,
            max             = self.max,
            min             = self.min,
            bitrate         = self.bitrate
        )

    def is_compatible_with(self, other):
        if self.bitrate != other.bitrate:
            raise ValueError('Statistics have different bitrates')
        if self._version != VERSION:
            raise ValueError('Statistics version ' + self._version + ' does not match lib version')
        if self._version != other._version:
            raise ValueError('Statistics have different bitrates')
        if type(self) != type(other):
            raise ValueError('Type mismatch: cannot union ' + str(type(self)) + ' with ' + str(type(other)))
        return True

    def _confirm_self_consistency(self):
        if self._version != VERSION:
            raise ValueError('Statistics version ' + self._version + ' does not match lib version')
        return True

    def __eq__(self, other):
        try:
            self.is_compatible_with(other)
        except ValueError:
            return False
        return (
            np.array_equal(self.sum,    other.sum)      and
            np.array_equal(self.sum_sq, other.sum_sq)   and
            np.array_equal(self.max,    other.max)      and
            np.array_equal(self.min,    other.min)
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __add__(self, other):
        return type(self).union(self, other)

class Report(object):
    """
    A class for generating reports on data integrity. Should be extended to
    create reports specific to different types of data, e.g. IRIGBReport
    and DuoToneReport.
    """
    def __init__(self,
            time_intervals  = TimeIntervalSet(),
            statistics      = Statistics(),
            histogram       = Histogram(),
            bitrate         = DEFAULT_BITRATE,
            version         = VERSION):
        self.time_intervals = time_intervals
        self.statistics     = statistics
        self.histogram      = histogram
        self.bitrate        = bitrate
        self._version       = version
        self._confirm_self_consistency()

    def _confirm_self_consistency(self):
        if not (self.bitrate == self.statistics.bitrate == self.histogram.bitrate):
            raise ValueError('Report constituents have different bitrates')
        if not (self._version == self.time_intervals._version == self.statistics._version == self.histogram._version):
            raise ValueError('Report constituents have different versions')
        if self._version != VERSION:
            raise ValueError('Report version ' + self._version + ' does not match lib version')
        if type(self.time_intervals) != TimeIntervalSet:
            raise ValueError('self.time_intervals must be of type TimeIntervalSet')
        if type(self.statistics) != Statistics:
            raise ValueError('self.statistics must be of type Statistics')
        if type(self.histogram) != Histogram:
            raise ValueError('self.histogram must be of type Histogram')

# TODO: DT and IRIG report classes; everything should fit into a report;
# a report contains both statistics and histogram classes.
