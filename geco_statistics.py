import sys
import bisect
import os
import subprocess
import datetime
import numpy as np

VERSION = '0.0.0'

# could use the interval package, but would be one more external dependency
class TimeIntervalSet:
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
                self.is_self_consistent()
        elif intervalSet == start == end == None or start == end:
            self._data = []
        elif start < end:
            self._data = [float(start), float(end)]
            self.remove_empty_sets()
            self.is_self_consistent()
        else:
            raise ValueError('Invalid combination of arguments. See documentation.')

    def union(self, other):
        """
        Return the union of the current set of intervals with some other set.

        Returns a new TimeIntervalSet instance without modifying the input
        arguments.
        """
        self.is_self_consistent()
        other.is_self_consistent()
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
        self.is_self_consistent()
        other.is_self_consistent()
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
        # TODO

    def complement_with_respect_to(self, other):
        """
        Return the complement of the current set of intervals with respect to
        another set.

        Returns a new TimeIntervalSet instance without modifying the input
        arguments.
        """
        self.is_self_consistent()
        other.is_self_consistent()
        raise Exception('not yet defined')
        # TODO

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
        self.is_self_consistent() # check
        i = 0
        while i < len(self._data) - 1:
            if self._data[i] == self._data[i+1]:
                self._data.pop(i) # remove this instance of the value...
                self._data.pop(i) # and the one to its right.
            else:
                i += 1           # not a copy, move on to the next one

    def is_self_consistent(self):
        'Check that this instance has form consistent with the class spec'
        if type(self._data) != list:
            raise Exception('TimeIntervalSet corrupted: data not a list')
        elif sorted(self._data) != self._data:
            raise Exception('TimeIntervalSet corrupted: data not sorted')
        elif len(self._data) % 2 != 0:
            raise Exception('TimeIntervalSet corrupted: odd number of endpoints')
        return True

    def clone(self):
        return TimeIntervalSet(self._data)

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

    def print_human_readable_dates(self):
        """
        Print the contained time intervals in an immediately human-readable
        form, assuming that the time endpoints that comprise this instance
        are GPS times. For example,

            [1135825217, 1135825219) U [1135825220, 1135825222)

        will be printed in the more comprehensible form:

            [Sun Jan 03 03:00:00 GMT 2016, Sun Jan 03 03:00:02 GMT 2016) U
            [Sun Jan 03 03:00:03 GMT 2016, Sun Jan 03 03:00:05 GMT 2016)

        """
        times = [int(x) for x in self._data]
        raise Exception('not yet defined')
        #TODO will rely on lalapps_tconvert for implementation

    def __eq__(self, other):
        return self._data == other._data

    def __ne__(self, other):
        return self._data != other._data

    def __len__(self):
        return len(self._data)

    def __str__(self):
        self.is_self_consistent()
        if self.__len__() == 0:
            return '{}'
        starts = self._data[0::2]
        ends   = self._data[1::2]
        string = '[' + str(starts[0]) + ', ' + str(ends[0]) + ')'
        for i in range(1, len(starts)):
            string += ' U [' + str(starts[i]) + ', ' + str(ends[i]) + ')'
        return string

class Statistics:
    def __init__(self, hist_range, bitrate=16384, hist_num_bins=256):

        # make sure hist_range is an ordered pair of numbers
        if not len(hist_range) == 2:
            raise ValueError('second argument (hist_range) must have length 2')
        elif hist_range[0] >= hist_range[1]:
            raise ValueError('minimum value of histogram bin range must be smaller than max')

        # these should actually be class properties for subclasses of Statistics
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
        self._version = VERSION

#TODO: DT and IRIG statistics subclasses
