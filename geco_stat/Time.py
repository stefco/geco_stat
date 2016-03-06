# -*- coding: utf-8 -*-

import bisect
import subprocess
import numpy as np      # >=1.10.4
from geco_stat._version import __version__, __release__
from geco_stat.Interface import ReportInterface
from geco_stat.Exceptions import VersionException

# TODO: Make PlottableInterface


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

    def __init__(self, intervalSet=None, start=None, end=None,
                 version=__version__):
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
        if version != self.__version__:
            raise VersionException()
        if type(intervalSet) == list or type(intervalSet) == np.ndarray:
            if len(intervalSet) % 2 != 0:
                raise ValueError('intervalSet set must have even length (equal '
                                 'starts and ends)')
            elif not np.array_equal(sorted(intervalSet), intervalSet):
                raise ValueError('intervalSet must be sorted')
            else:
                self._data = np.array([float(x) for x in intervalSet])
                self.remove_empty_sets()
                self._assert_self_consistent()
        elif (intervalSet is None and start is None and end is None or
                start == end):
            self._data = np.array([])
        elif start < end:
            self._data = np.array([float(start), float(end)])
            self.remove_empty_sets()
            self._assert_self_consistent()
        else:
            raise ValueError('Invalid combination of arguments. '
                             'See documentation.')

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
        for i in range(0, len(other)//2):
            # this part is (mostly)  shared between set algebra methods
            start  = other.to_ndarray()[2*i]
            end    = other.to_ndarray()[2*i + 1]
            bnds   = result.__left_and_right_bounds__(start, end)
            left   = bnds[0] % 2
            right  = bnds[1] % 2
            npcat  = np.concatenate # give this a shorter name
            # the conditional responses are unique to each set algebra method
            if left == 0 and right == 1:
                result._data = npcat((result.to_ndarray()[0:bnds[0]],
                                      [start, end],
                                      result.to_ndarray()[bnds[1]+1:]))
            elif left == 0 and right == 0:
                result._data = npcat((result.to_ndarray()[0:bnds[0]],
                                      [start],
                                      result.to_ndarray()[bnds[1]+1:]))
            elif left == 1 and right == 1:
                result._data = npcat((result.to_ndarray()[0:bnds[0]],
                                      [end],
                                      result.to_ndarray()[bnds[1]+1:]))
            elif left == 1 and right == 0:
                result._data = npcat((result.to_ndarray()[0:bnds[0]],
                                      result.to_ndarray()[bnds[1]+1:]))
            result.remove_empty_sets()
        return result

    def to_ndarray(self):
        """
        Return a numpy.ndarray whose value can be used as an argument to this
        class's constructor to recreate an equivalent instance. For example,

        >>> TimeIntervalSet(numpy.array([0,1])).to_ndarray()
        array([ 0.,  1.])
        """
        return self._data

    @staticmethod
    def __find_frame_file_gps_start_time__(gps_time):
        """
        Get the GPS Time representing the START time of the frame file
        containing data for the time represented by the argument, which
        must also be in GPS Time format.

        Frame files always start at times that are integer multiples of
        64, so this is just a convenience function for rounding down to
        the nearest multiple of 64.
        """
        ans = np.floor(gps_time / 64.) * 64
        if ans % 1 != 0:
            raise ValueError("Out of precision in floats, answer should be "
                             "an integer")
        return ans

    @staticmethod
    def __find_frame_file_gps_end_time__(gps_time):
        """
        Get the GPS Time representing the END time of the frame file
        containing data for the time represented by the argument, which
        must also be in GPS Time format.

        Frame files always start at times that are integer multiples of
        64, so this is just a convenience function for rounding up to
        the nearest multiple of 64.
        """
        ans = np.ceil(gps_time / 64.) * 64
        if ans % 1 != 0:
            raise ValueError("Out of precision in floats, answer should "
                             "be an integer")
        return ans

    @staticmethod
    def tconvert(input_time):
        """
        Take either a numerical input (representing gps time) or a string input
        (representing UTC time) and return the opposite. For example:

            tconvert('Oct 30 00:00:00 GMT 2015')

        returns

            1130198417

        and

            tconvert(1130198417)

        returns

            'Oct 30 00:00:00 GMT 2015'

        """
        if type(input_time) is str:
            dump = subprocess.Popen(
                ["lalapps_tconvert",str(input_time)], stdout=subprocess.PIPE)
            converted_time = dump.communicate()[0]
            return int(converted_time) # should be an int; if not, that's bad
        else:
            dump = subprocess.Popen(["lalapps_tconvert",str(
                int(input_time))], stdout=subprocess.PIPE)
            converted_time = dump.communicate()[0]
            return converted_time

    def round_to_frame_times(self):
        """
        Return a TimeIntervalSet that is a superset of of this TimeIntervalSet
        and which perfectly overlaps with the data contained in a set of frame
        files. Since frame files start at times that are integer multiples of,
        this is tantamount to rounding the start times up and the end times
        down.
        """
        cls = type(self)
        rounded_times = cls()
        for i in range(0, len(self)//2):
            rounded_times += cls([
                cls.__find_frame_file_gps_start_time__(self.to_ndarray()[2*i]),
                cls.__find_frame_file_gps_end_time__(self.to_ndarray()[2*i+1])
            ])
        return rounded_times

    def split_into_frame_file_intervals(self):
        """
        Return a list of TimeIntervalSets corresponding to time intervals
        covered by the frame files covering this time range. For example,

        >>> TSet = geco_stat.TimeIntervalSet
        >>> TSet([64,192,256,320]).split_into_frame_file_intervals()
        [geco_stat.TimeIntervalSet([64.0, 128.0]), geco_stat.TimeIntervalSet([128.0, 192.0]), geco_stat.TimeIntervalSet([256.0, 320.0])]

        The input TimeIntervalSet instance must start and end on a valid
        frame file time (an integer multiple of 64) or else an error will
        be raised.
        """
        if self.round_to_frame_times() != self:
            raise ValueError("Can only split a rounded time interval")
        frame_intervals = []
        for i in range(0, len(self)//2):
            if int(self.to_ndarray()[2*i]) != self.to_ndarray()[2*i]:
                raise ValueError("Out of precision in floats, answer should "
                                 "be an integer")
            if int(self.to_ndarray()[2*i+1]) != self.to_ndarray()[2*i+1]:
                raise ValueError("Out of precision in floats, answer should "
                                 "be an integer")
            for start_time in range(int(self.to_ndarray()[2*i]),
                                    int(self.to_ndarray()[2*i+1]), 64):
                frame_intervals.append(type(self)([start_time, start_time+64]))
        return frame_intervals

    @classmethod
    def from_human_readable_strings(cls, readable_string_list):
        """
        Take an iterable consisting of pairs of strings and return a timeseries
        corresponding to those times. The input iterable should be flat
        (one-dimensional) and have an even number of entries, or else an error
        will result. For example, use as input:

            ['Oct 30 00:00:00 GMT 2015', 'Oct 30 00:02:00 GMT 2015']

        which will return a time interval corresponding to the given time
        strings. The conversion to GPS is carried out by lalapps_tconvert,
        so formatting must be comprehensible to that program.

        Note that no rounding occurs, so if you are going to use these times
        to find gravitational wave frame files, you should not use the resulting
        numerical values but find another way to generate a list of
        gravitational wave frame file start times (like using
        self.round_to_frame_times).
        """
        times = []
        for s in readable_string_list:
            if not isinstance(s, str):
                raise ValueError('from_human_readable_strings() must use '
                                 'strings as input')
            times.append(cls.tconvert(s))
        return cls(times)

    def intersection(self, other):
        """
        Return the intersection of the current set of intervals with some other
        set.

        Returns a new TimeIntervalSet instance without modifying the input
        arguments.
        """
        self._assert_self_consistent()
        other._assert_self_consistent()
        if len(other) == 0 or len(self) == 0:
            return TimeIntervalSet()
        result = TimeIntervalSet()
        for i in range(0, len(other)//2):
            # this part is (mostly)  shared between set algebra methods
            start  = other.to_ndarray()[2*i]
            end    = other.to_ndarray()[2*i + 1]
            bnds   = self.__left_and_right_bounds__(start, end) # this differs
            left   = bnds[0] % 2
            right  = bnds[1] % 2
            npcat  = np.concatenate # give this a shorter name
            # the conditional responses are unique to each set algebra method
            if left == 0 and right == 1:
                result._data = npcat((result.to_ndarray(),
                                      self.to_ndarray()[bnds[0]:bnds[1]+1]))
            elif left == 0 and right == 0:
                result._data = npcat((result.to_ndarray(),
                                      self.to_ndarray()[bnds[0]:bnds[1]+1],
                                      [end]))
            elif left == 1 and right == 1:
                result._data = npcat((result.to_ndarray(), [start],
                                      self.to_ndarray()[bnds[0]:bnds[1]+1]))
            elif left == 1 and right == 0:
                result._data = npcat((result.to_ndarray(), [start],
                                      self.to_ndarray()[bnds[0]:bnds[1]+1],
                                      [end]))
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
        self._assert_self_consistent()
        other._assert_self_consistent()
        if self.union(other) != other:
            raise ValueError('Can only take complement with respect to a '
                             'superset.')
        if len(self) == 0:
            return other
        result = TimeIntervalSet()
        for i in range(0, len(other)//2):
            # this part is (mostly)  shared between set algebra methods
            start  = other.to_ndarray()[2*i]
            end    = other.to_ndarray()[2*i + 1]
            bnds   = self.__left_and_right_bounds__(start, end) # this differs
            left   = bnds[0] % 2
            right  = bnds[1] % 2
            npcat  = np.concatenate # give this a shorter name
            # the conditional responses are unique to each set algebra method
            if left == 0 and right == 1:
                result._data = npcat((result.to_ndarray(), [start],
                                      self.to_ndarray()[bnds[0]:bnds[1]+1],
                                      [end]))
            elif left == 0 and right == 0:
                result._data = npcat((result.to_ndarray(), [start],
                                      self.to_ndarray()[bnds[0]:bnds[1]+1]))
            elif left == 1 and right == 1:
                result._data = npcat((result.to_ndarray(),
                                      self.to_ndarray()[bnds[0]:bnds[1]+1],
                                      [end]))
            elif left == 1 and right == 0:
                result._data = npcat((result.to_ndarray(),
                                      self.to_ndarray()[bnds[0]:bnds[1]+1]))
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

        L is then used to determine a merge strategy for the union,
        intersection, or complement of S with respect to [a, b).

        For the sake of simplicity of implementation, this function only accepts
        positive even length lists of start and end points. In other words, an
        error will be raised if the user tries passing an empty TimeIntervalSet.
        """
        if len(self.to_ndarray()) == 0:
            raise ValueError('Cannot use an empty TimeIntervalSet.')
        l = bisect.bisect_left(self.to_ndarray(), a)
        r = bisect.bisect_right(self.to_ndarray(), b) - 1
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
        self._assert_self_consistent() # check
        i = 0
        while i < len(self.to_ndarray()) - 1:
            if self.to_ndarray()[i] == self.to_ndarray()[i+1]:
                self._data = np.delete(self.to_ndarray(), np.s_[i:i+2])
            else:
                i += 1           # not a copy, move on to the next one

    def _confirm_unionability(self, other):
        if type(self) != type(other):
            raise ValueError('Type mismatch: cannot union ' +
                             str(type(self)) + ' with ' + str(type(other)))
        if self.__version__ != other.__version__:
            raise ValueError('TimeIntervalSets have different versions')
        return True

    def _assert_self_consistent(self):
        'Check that this instance has form consistent with the class spec'
        if type(self.to_ndarray()) != np.ndarray:
            raise Exception('TimeIntervalSet corrupted: '
                            'data not a numpy.ndarray')
        elif not np.array_equal(sorted(self.to_ndarray()), self.to_ndarray()):
            raise Exception('TimeIntervalSet corrupted: data not sorted')
        elif len(self.to_ndarray()) % 2 != 0:
            raise Exception('TimeIntervalSet corrupted: odd number '
                            'of endpoints')
        return True

    def __clone__(self):
        return type(self)(self.to_ndarray())

    def combined_length(self):
        'Get the combined length of all time intervals in this TimeIntervalSet.'
        if len(self.to_ndarray()) == 0:
            return 0
        starts = self.to_ndarray()[0::2]
        ends   = self.to_ndarray()[1::2]
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
        times = [str(int(x)) for x in self.to_ndarray()]
        self._assert_self_consistent()
        tstring = ""
        i = 0
        for time in times:
            dump = subprocess.Popen(
                ["lalapps_tconvert",time], stdout=subprocess.PIPE)
            if i == 0:
                tstring += '[' + dump.communicate()[0][:-1] + ', '
                i = 1
            else:
                tstring += dump.communicate()[0][:-1] + ') U\n'
                i = 0
        tstring = tstring[:-3] # shave off the last U character and newline
        return tstring

    @classmethod
    def __from_dict__(cls, d):
        return cls(d['data'], version=d['version'])

    def __to_dict__(self):
        return {'data': np.array(self.to_ndarray()),
                'version': self.__version__}

    def __eq__(self, other):
        return np.array_equal(self.to_ndarray(), other.to_ndarray())

    def __len__(self):
        return len(self.to_ndarray())

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
        self._assert_self_consistent()
        if len(self) == 0:
            return '{}'
        starts = self.to_ndarray()[0::2]
        ends   = self.to_ndarray()[1::2]
        string = '[' + str(starts[0]) + ', ' + str(ends[0]) + ')'
        for i in range(1, len(starts)):
            string += ' U [' + str(starts[i]) + ', ' + str(ends[i]) + ')'
        return string

    def __repr__(self):
        self._assert_self_consistent()
        return __name__ + '.TimeIntervalSet(' + repr(list(self._data)) + ')'

    # TODO this shouldn't circularly Timeseries class... not elegant
    def from_timeseries(self, timeseries):
        """Just clone the TimeIntervalSet belonging to the Timeseries"""
        return timeseries.time_intervals.clone()

