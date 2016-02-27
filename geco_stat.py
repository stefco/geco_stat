import sys
import types
import bisect
import os
import subprocess
import datetime
import h5py             # >=2.5.0
import abc
import numpy as np      # >=1.10.4
from version import *

DEFAULT_BITRATE = 16384

class VersionError(Exception):
    """
    For when the user attempts to instantiate an object using a
    datastructure from a different version number of the class.
    """

class MissingChannelDataException(Exception):
    """
    For when an attempt has been made to fetch a timeseries for
    a given time interval, but no data has been found, or the
    data request has timed out.
    """

class Timeseries(np.ndarray):
    """
    A thin wrapper for ndarrays, adding in a couple of convenience methods
    used to create new instances from gravitational wave frame files.
    """

    @classmethod
    def from_time_and_channel_name(cls, channel_name, time_interval, bitrate=DEFAULT_BITRATE):
        """
        Load a timeseries using this channel_name and time_interval.

        The time_interval argument must, at the moment, correspond to a single
        gravitational wave frame file. Future implementations might change this.
        """
        frame_path = cls.locate_frame_file(channel_name, time_interval)
        return cls.from_frame_file(channel_name, frame_path, time_interval, bitrate)

    @classmethod
    def from_frame_file(cls, channel_name, path, time_intervals, bitrate=DEFAULT_BITRATE):
        """
        Load channel from file path to array.

        If a channel doesn't exist within the
        frame file located at the specified path, this function will return None.
        Otherwise, it returns an ndarray with one row for each second of data in the
        frame file.
        """

        # make sure path exists
        if not os.path.exists(path):
            raise ValueError('Path does not exist: ' + path)

        # set up the processes for acquiring and processing the data
        dump = subprocess.Popen(["framecpp_dump_channel","--channel",channel_name,path], stdout=subprocess.PIPE)
        data_string = dump.communicate()[0]
        print now() + ' Timeseries retrieved, beginning processing.'

        # remove headers from the data
        formatted_data_string = cls.__remove_header_and_text__(data_string)

        # if the string is empty, the channel didn't exist. return None.
        if formatted_data_string == '':
            raise MissingChannelDataException()

        # instantiate numpy array and return it; will have number of rows equal to
        # the number of seconds in a frame file and number of columns equal to the
        # bitrate of the channel.
        ans = np.fromstring(formatted_data_string, sep=',').reshape((64, bitrate)).view(cls)
        ans.time_intervals = time_intervals
        ans.bitrate = bitrate
        return ans

    def get_num_seconds(self):
        """
        Get the number of seconds worth of data in this frame file.
        """
        assert self.shape[0] == self.time_intervals.combined_length(), 'mismatch between time_interval length and number of seconds of data'
        return self.shape[0]

    @staticmethod
    def locate_frame_file(channel_name, time_interval):
        """
        Find the gravitational wave frame file corresponding to a particular
        time interval for a particular channel name.
        """
        assert time_interval.round_to_frame_times() == time_interval, 'Must pick a time interval that is already rounded to frame times.'
        assert time_interval.combined_length() == 64, 'TimeIntervalSet must correspond to only a single frame file.'
        assert len(time_interval) == 2, 'TimeIntervalSet must contain only one continuous interval.'
        assert type(channel_name) == types.StringType, 'locate_frame_file() channel_name must be a string.'
        assert isinstance(time_interval, TimeIntervalSet), 'locate_frame_file() time_interval must be a TimeIntervalSet'

        detector_prefix = channel_name[0]
        dump = subprocess.Popen([
                'gw_data_find',
                '-o', detector_prefix,
                '-t', detector_prefix + '1_R',
                '-s', time_interval._data[0],
                '-e', time_interval._data[1],
                '-u', 'file'], stdout=subprocess.PIPE)
        frame_path = dump.communicate()[0]
        assert frame_path[0:15] == 'file://localhost', 'expected file://localhost prefix output from gw_data_find, got %s' % frame_path[0:15]
        frame_path = frame_path[16:]
        assert os.path.exists(frame_path), 'gw_data_find returned faulty path %s' % frame_path
        return frame_path

    @staticmethod
    def __remove_lines__(string, num_lines):
        """
        remove first n lines of a string
        """
        i = 0
        n = 0
        l = len(string)
        while n < num_lines:
            i = string.find('\n', i+1)
            # if a newline isn't found, this means there are no new lines left.
            if i == -1:
                return ""
            # if the string ends on a newline, return empty string.
            elif i+1 == l:
                return ""
            n += 1
        return string[i+1:]

    @staticmethod
    def __remove_header_and_text__(string):
        """
        Delete first 6 lines; all spaces; and the word 'Data:' which precedes the
        numerical data.

        (This replaces sed and tr in the original implementation with native python.)
        """
        return __remove_lines__(string, 6).translate(None, 'Dat: ')

# could use the interval package, but would be one more external dependency
class ReportInterface(object):
    "Abstract interface used by all geco_statistics classes"
    __metaclass__  = abc.ABCMeta
    __version__ = __version__

    def union(self, other):
        "Aggregate these two instances. Must be of compatible type."
        self._assert_self_consistent()
        other._assert_self_consistent()
        self._confirm_unionability(other)
        return self.__union__(other)

    def clone(self):
        "Create a new object that is an exact copy of this instance."
        self._assert_self_consistent()
        return self.__clone__()

    def save_hdf5(self, filename):
        """Save this instance to an hdf5 file."""
        self.__save_dict_to_hdf5__(self.__to_dict__())

    @classmethod
    def load_hdf5(cls, filename):
        """Load an instance saved in an hdf5 file."""
        return cls.__from_dict__(cls.__load_dict_from_hdf5__(filename))

    @classmethod
    def __save_dict_to_hdf5__(cls, dic, filename):
        """
        Save a dictionary whose contents are only strings, np.float64, np.int64,
        np.ndarray, and other dictionaries following this structure
        to an HDF5 file. These are the sorts of dictionaries that are meant
        to be produced by the ReportInterface__to_dict__() method. The saved
        dictionary can then be loaded using __load_dict_to_hdf5__(), and the
        contents of the loaded dictionary will be the same as those of the
        original:

        >>> ex = {
        >>>     'name': 'stefan',
        >>>     'age':  np.int64(24),
        >>>     'fav_numbers': np.array([2,4,4.3]),
        >>>     'fav_tensors': {
        >>>         'levi_civita3d': np.array([
        >>>             [[0,0,0],[0,0,1],[0,-1,0]],
        >>>             [[0,0,-1],[0,0,0],[1,0,0]],
        >>>             [[0,1,0],[-1,0,0],[0,0,0]]
        >>>         ]),
        >>>         'kronecker2d': np.identity(3)
        >>>     }
        >>> }
        >>> ReportInterface.__save_dict_to_hdf5__(ex, 'foo.hdf5')
        >>> loaded = ReportInterface.__load_dict_from_hdf5__('foo.hdf5')
        >>> np.testing.assert_equal(loaded, ex), "HDF5 dict saving utilities failing."
        True
        """

        if os.path.exists(filename):
            raise ValueError('File %s exists, will not overwrite.' % filename)
        with h5py.File(filename, 'w') as h5file:
            cls.__recursively_save_dict_contents_to_group__(h5file, '/', dic)

    @classmethod
    def __recursively_save_dict_contents_to_group__(cls, h5file, path, dic):
        """
        Take an already open HDF5 file and insert the contents of a dictionary
        at the current path location. Can call itself recursively to fill
        out HDF5 files with the contents of a dictionary.
        """
        if not type(dic) is types.DictionaryType:
            raise ValueError("must provide a dictionary")
        if not type(path) is types.StringType:
            raise ValueError("path must be a string")
        if not type(h5file) is h5py._hl.files.File:
            raise ValueError("must be an open h5py file")
        for key in dic:
            if not type(key) == types.StringType:
                raise ValueError("dict keys must be strings to save to hdf5")
            if type(dic[key]) in (np.int64, np.float64, types.StringType):
                h5file[path + key] = dic[key]
                if not h5file[path + key].value == dic[key]:
                    raise ValueError(
                        'The data representation in the HDF5 file does not match the original dict.'
                    )
            if type(dic[key]) is np.ndarray:
                h5file[path + key] = dic[key]
                if not np.array_equal(h5file[path + key].value, dic[key]):
                    raise ValueError(
                        'The data representation in the HDF5 file does not match the original dict.'
                    )
            elif type(dic[key]) is types.DictionaryType:
                cls.__recursively_save_dict_contents_to_group__(h5file, path + key + '/', dic[key])

    @classmethod
    def __load_dict_from_hdf5__(cls, filename):
        """
        Load a dictionary whose contents are only strings, floats, ints,
        numpy arrays, and other dictionaries following this structure
        from an HDF5 file. These dictionaries can then be used to reconstruct
        ReportInterface subclass instances using the
        ReportInterface.__from_dict__() method.
        """
        with h5py.File(filename, 'r') as h5file:
            return cls.__recursively_load_dict_contents_from_group__(h5file, '/')

    @classmethod
    def __recursively_load_dict_contents_from_group__(cls, h5file, path):
        """
        Load contents of an HDF5 group. If further groups are encountered,
        treat them like dicts and continue to load them recursively.
        """
        ans = {}
        for key, item in h5file[path].items():
            if type(item) is h5py._hl.dataset.Dataset:
                ans[key] = item.value
            elif type(item) is h5py._hl.group.Group:
                ans[key] = cls.__recursively_load_dict_contents_from_group__(h5file, path + key + '/')
        return ans

    @abc.abstractmethod
    def from_timeseries(self, timeseries):
        """
        Create a compatible object using timeseries data as input. This is
        an instance method, meant to create a new object compatible with
        the current instance; this approach allows for a trivially
        simple method interface, requiring only the timeseries array itself
        as input.

        The timeseries argument can be composed of multiple rows, representing
        multiple seconds, worth of data. It can also simply consist of an
        integer number of seconds worth of data. Consequently, the length of
        the (flattened) input timeseries must be an integer multiple of the
        bitrate. This is tested by the abstract method; subclasses can
        extend it.
        """
        l = len(timeseries.flatten())
        assert l % self.bitrate == 0, 'Flattened timeseries length must be integer mult of bitrate.'
        assert l > 0, 'Cannot pass an empty timeseries.'

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
    def _confirm_unionability(self, other):
        "Make sure these two instances can be unioned."

    @abc.abstractmethod
    def _assert_self_consistent(self):
        "Make sure this instance is self-consistent."

    @abc.abstractmethod
    def __eq__(self, other):
        "Instances must have a way of determining equality."

    def __ne__(self, other):
        return not self == other

    def __add__(self, other):
        'Addition can be used as a shorthand for union.'
        return type(self).union(self, other)

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
        Create some sort of verbose, human-readable text summary for the information
        content of this object. Should return a string.
        """

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

    def __init__(self, intervalSet=None, start=None, end=None, version=__version__):
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
            raise VersionError()
        if type(intervalSet) == list or type(intervalSet) == np.ndarray:
            if len(intervalSet) % 2 != 0:
                raise ValueError('intervalSet set must have even length (equal starts and ends)')
            elif not np.array_equal(sorted(intervalSet), intervalSet):
                raise ValueError('intervalSet must be sorted')
            else:
                self._data = np.array([float(x) for x in intervalSet])
                self.remove_empty_sets()
                self._assert_self_consistent()
        elif intervalSet == start == end == None or start == end:
            self._data = np.array([])
        elif start < end:
            self._data = np.array([float(start), float(end)])
            self.remove_empty_sets()
            self._assert_self_consistent()
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
                result._data = np.concatenate((result._data[0:bounds[0]], [start, end], result._data[bounds[1]+1:]))
            elif left == 0 and right == 0:
                result._data = np.concatenate((result._data[0:bounds[0]], [start], result._data[bounds[1]+1:]))
            elif left == 1 and right == 1:
                result._data = np.concatenate((result._data[0:bounds[0]], [end], result._data[bounds[1]+1:]))
            elif left == 1 and right == 0:
                result._data = np.concatenate((result._data[0:bounds[0]], result._data[bounds[1]+1:]))
            result.remove_empty_sets()
        return result

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
        assert ans % 1 == 0, "Out of precision in floats, answer should be integer"
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
        assert ans % 1 == 0, "Out of precision in floats, answer should be integer"
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
            dump = subprocess.Popen(["lalapps_tconvert",str(input_time)], stdout=subprocess.PIPE)
            converted_time = dump.communicate()[0]
            return int(converted_time) # should be an int; if not, that's bad
        else:
            dump = subprocess.Popen(["lalapps_tconvert",str(int(input_time))], stdout=subprocess.PIPE)
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
        for i in range(0, len(self)/2):
            rounded_times += cls([
                cls.__find_frame_file_gps_start_time__(self._data[2*i]),
                cls.__find_frame_file_gps_end_time__(self._data[2*i+1])
            ])
        return rounded_times

    def split_into_frame_file_intervals(self):
        """
        Return a list of TimeIntervalSets corresponding to time intervals
        covered by the frame files covering this time range. For example,

        >>> TSet = geco_stat.TimeIntervalSet
        >>> geco_stat.TimeIntervalSet([64,192,256,320]).split_into_frame_file_intervals()
        [geco_stat.TimeIntervalSet([64.0, 128.0]), geco_stat.TimeIntervalSet([128.0, 192.0]), geco_stat.TimeIntervalSet([256.0, 320.0])]

        The input TimeIntervalSet instance must start and end on a valid
        frame file time (an integer multiple of 64) or else an error will
        be raised.
        """
        assert self.round_to_frame_times() == self, "Can only split a rounded time interval"
        frame_intervals = []
        for i in range(0, len(self)/2):
            assert int(self._data[2*i]) == self._data[2*i], "Out of precision in floats, answer should be integer"
            assert int(self._data[2*i+1]) == self._data[2*i+1], "Out of precision in floats, answer should be integer"
            for start_time in range(int(self._data[2*i]), int(self._data[2*i+1]), 64):
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
            assert type(s) is types.StringType, 'from_human_readable_strings() must use strings as input'
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
        self._assert_self_consistent()
        other._assert_self_consistent()
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
        self._assert_self_consistent() # check
        i = 0
        while i < len(self._data) - 1:
            if self._data[i] == self._data[i+1]:
                self._data = np.delete(self._data, np.s_[i:i+2])
            else:
                i += 1           # not a copy, move on to the next one

    def _confirm_unionability(self, other):
        if type(self) != type(other):
            raise ValueError('Type mismatch: cannot union ' + str(type(self)) + ' with ' + str(type(other)))
        if self.__version__ != other.__version__:
            raise ValueError('TimeIntervalSets have different versions')
        return True

    def _assert_self_consistent(self):
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
        self._assert_self_consistent()
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
    def __from_dict__(cls, d):
        return cls(d['data'], version=d['version'])

    def __to_dict__(self):
        return {'data': np.array(self._data), 'version': self.__version__}

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
        self._assert_self_consistent()
        if len(self) == 0:
            return '{}'
        starts = self._data[0::2]
        ends   = self._data[1::2]
        string = '[' + str(starts[0]) + ', ' + str(ends[0]) + ')'
        for i in range(1, len(starts)):
            string += ' U [' + str(starts[i]) + ', ' + str(ends[i]) + ')'
        return string

    def __repr__(self):
        self._assert_self_consistent()
        return __name__ + '.TimeIntervalSet(' + repr(list(self._data)) + ')'

    def from_timeseries(self, timeseries):
        """Just clone the TimeIntervalSet belonging to the Timeseries"""
        return timeseries.time_intervals.clone()

# TODO: Make PlottableInterface
class AbstractReportData(ReportInterface):
    "Abstract class for aggregated data. All instances must implement interface."
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
            bitrate         = DEFAULT_BITRATE,
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
            raise VersionError()
        elif hist_range[0] >= hist_range[1]:
            raise ValueError('minimum value of histogram bin range must be smaller than max')

        # set values to "empty" histograms
        if hist == None:
            hist = np.zeros((hist_num_bins, bitrate), dtype=np.int64)

        assert np.int64(hist_num_bins) == hist_num_bins, 'hist_num_bins must be an integer'
        self.hist_num_bins  = np.int64(hist_num_bins)
        assert len(hist_range) == 2
        self.hist_range     = np.array(hist_range)
        self.hist           = np.array(hist, copy=True) # Make sure this is a copy of the data
        self.hist_bins      = np.linspace(hist_range[0], hist_range[1], hist_num_bins+1)
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
        if self.hist_range != other.hist_range or self.hist_num_bins != other.hist_num_bins:
            raise ValueError('Histograms have different bin edges')
        if self.bitrate != other.bitrate:
            raise ValueError('Histograms have different bitrates')
        if self.__version__ != other.__version__:
            raise ValueError('Histograms have different versions')
        if type(self) != type(other):
            raise ValueError('Type mismatch: cannot union ' + str(type(self)) + ' with ' + str(type(other)))
        return True

    def _assert_self_consistent(self):
        if self.__version__ != __version__:
            raise ValueError('Histogram version ' + self.__version__ + ' does not match lib version')
        assert self.hist_bins == np.linspace(self.hist_range[0], self.hist_range[1], self.hist_num_bins+1)
        assert self.t_ticks == np.linspace(0,1,self.bitrate+1)
        assert np.int64(self.bitrate) == self.bitrate, 'bitrate must be an integer'
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
        assert xedges == self.hist_bins, 'xedges should be the histogram bins'
        assert yedges == self.t_ticks, 'yedges should be the t_ticks'
        assert self.bitrate == timeseries.bitrate, 'timeseries and histogram must have same bitrate'
        self._assert_self_consistent()
        return type(self)(
            hist            = hist,
            hist_range      = self.hist_range,
            hist_num_bins   = self.hist_num_bins,
            bitrate         = self.bitrate)

    def __eq__(self, other):
        if self.hist_range != other.hist_range or self.hist_num_bins != other.hist_num_bins:
            return False
        if self.bitrate != other.bitrate:
            return False
        if self.__version__ != other.__version__:
            return False
        if type(self) != type(other):
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
            bitrate         = DEFAULT_BITRATE,
            version         = __version__):
        """
        All properties have default values corresponding to an empty statistics
        set; they can be individually overridden.
        """
        if version != self.__version__:
            raise VersionError()

        # set values of sum, sum_sq, and the histograms, since these depend on
        # bitrate and hist_num_bins and hence cannot be set above
        if sum          == None: sum        = np.zeros(bitrate)
        if sum_sq       == None: sum_sq     = np.zeros(bitrate)
        if max          == None: max        = np.ones(bitrate) * np.finfo(np.float64).min # lowest possible max, cannot survive
        if min          == None: min        = np.ones(bitrate) * np.finfo(np.float64).max # same for min

        self.sum        = np.array(sum, copy=True).reshape((bitrate,))
        self.sum_sq     = np.array(sum_sq, copy=True).reshape((bitrate,))
        self.max        = np.array(max, copy=True).reshape((bitrate,))
        self.min        = np.array(min, copy=True).reshape((bitrate,))
        assert np.int64(num) == num, 'must provide an integer number of previous seconds'
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
        if type(self) != type(other):
            raise ValueError('Type mismatch: cannot union ' + str(type(self)) + ' with ' + str(type(other)))
        return True

    def _assert_self_consistent(self):
        assert self.sum.shape == (self.bitrate,), "sum should be vector with length equal to bitrate"
        assert self.sum_sq.shape == (self.bitrate,), "sum_sq should be vector with length equal to bitrate"
        assert self.max.shape == (self.bitrate,), "max should be vector with length equal to bitrate"
        assert self.min.shape == (self.bitrate,), "min should be vector with length equal to bitrate"
        assert np.int64(self.num) == self.num
        assert np.int64(self.bitrate) == self.bitrate, 'bitrate must be an integer'
        if self.__version__ != __version__:
            raise ValueError('Statistics version ' + self.__version__ + ' does not match lib version')
        if not ((self.bitrate,) == self.sum.shape == self.sum_sq.shape == self.max.shape == self.min.shape):
            raise ValueError('Statistics fields must be 1-D with length equal to bitrate')
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
        super(type(self), self).from_timeseries()
        return type(self)(
                sum     = timeseries.sum(0),
                sum_sq  = np.power(timeseries, 2).sum(0),
                max     = np.max(timeseries, 0),
                min     = np.min(timeseries, 0),
                num     = np.shape[0],
                bitrate = timeseries.bitrate)

    def __eq__(self, other):
        if self.bitrate != other.bitrate:
            return False
        if self.__version__ != other.__version__:
            return False
        if type(self) != type(other):
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
            bitrate         = DEFAULT_BITRATE,
            version         = __version__,
            time_intervals  = None,
            data            = None):

        if version != self.__version__:
            raise VersionError()

        assert np.int64(bitrate) == bitrate, 'bitrate must be an integer'
        self.bitrate = np.int64(bitrate)
        if time_intervals == None:
            self.time_intervals = TimeIntervalSet()
        else:
            self.time_intervals = time_intervals.clone()

        if data == None:
            data = self.__report_data_prototype__(bitrate)
        self._data = data               # data grouped here
        for key in data:                # instance attr pointers for convenience
            if hasattr(self, key):
                raise ValueError('AbstractReportData dictionary should not have attributes conflicting with AbstractReport attributes.')
            setattr(self, key, data[key])
        self._assert_self_consistent()

    @classmethod
    @abc.abstractmethod
    def __report_data_prototype__(cls, bitrate=DEFAULT_BITRATE):
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
        def __report_data_prototype__(cls, bitrate=DEFAULT_BITRATE)
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

        Define a method for testing whether a timeseries is anomalous. If so, the
        report generated from this timeseries will be unioned into report_anomalies_only.
        If not, the report generated from this timeseries will be unioned
        into report_sans_anomalies. In any case, the report will be unioned into
        report, which contains report data on the entire timeseries contained in
        the ReportSet.
        """

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

    def _confirm_unionability(self, other):
        if self.bitrate != other.bitrate:
            raise ValueError('Reports have different bitrates')
        if self.__version__ != other.__version__:
            raise ValueError('Reports have different versions')
        if type(self) != type(other):
            raise ValueError('Type mismatch: cannot union ' + str(type(self)) + ' with ' + str(type(other)))
        if set(self._data) != set(other._data):
            raise ValueError('AbstractReportData sets do not have matching key sets.')
        if self.time_intervals.intersection(other.time_intervals) != TimeIntervalSet():
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
                raise ValueError('key ' + str(key) + ' must be instance of AbstractReportData')
            self._data[key]._assert_self_consistent()
            if self.bitrate != self._data[key].bitrate:
                raise ValueError('Report constituents have different bitrates')
            if self.__version__ != self._data[key].__version__:
                raise ValueError('Report constituents have different versions')
        if not isinstance(self.time_intervals, TimeIntervalSet):
            raise ValueError('self.time_intervals must be an instance of TimeIntervalSet.')
        if self.__version__ != self.time_intervals.__version__:
            raise ValueError('time_intervals has different version than the Report itself')
        assert np.int64(self.bitrate) == self.bitrate, 'bitrate must be an integer'

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
            if not issubclass(report_data_class, ReportData):
                raise ValueError('Cannot reconstruct Report data; class property not a valid AbstractReportData subclass')
            data[key] = report_data_class.__from_dict__(data_dict[key])
        return cls(
            bitrate         = d['bitrate'],
            version         = d['version'],
            time_intervals  = TimeIntervalSet.__from_dict__(d['time_intervals']),
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
        if type(self) != type(other) or set(self._data) != set(other._data):
            return False
        if self.bitrate != other.bitrate or self.__version__ != other.__version__:
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
    that allow the user to distinguish between anomalous and typical time ranges in
    the input data.
    """

    # TODO Add notes, full intended time, current work block, and is_finished method
    def __init__(self,
            report_class_name,
            bitrate                 = DEFAULT_BITRATE,
            version                 = __version__,
            channel_name            = "blank_report",
            time_intervals          = None,
            report                  = None,
            report_anomalies_only   = None,
            report_sans_anomalies   = None,
            missing_times           = None):
        if version != self.__version__:
            raise VersionError()

        if type(report_class_name) is str:
            self.report_class_name = report_class_name
            if not self.get_report_class() is type:
                raise ValueError('report_class must be equal to the name of a ReportData class')
        else:
            raise ValueError('report_class must be a string')

        if time_intervals == None:
            self.time_intervals         = TimeIntervalSet()
        else:
            self.time_intervals         = time_intervals.clone()

        if missing_times == None:
            self.missing_times          = TimeIntervalSet()
        else:
            self.missing_times          = missing_times.clone()

        # All or none of the three reports must be provided as arguments,
        # otherwise it would be possible to initialize an inconsistent ReportSet.
        if None == report == report_anomalies_only == report_sans_anomalies:
            self.report                 = self.get_report_class()(bitrate=bitrate)
            self.report_anomalies_only  = self.get_report_class()(bitrate=bitrate)
            self.report_sans_anomalies  = self.get_report_class()(bitrate=bitrate)
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
        this function simply returns the Report class corresponding to the class
        name passed as an argument.
        """
        if not type(self) is str:
            self = self.report_class_name
        return globals()[self]

    @staticmethod
    def from_time_and_channel_name(
            report_class_name, channel_name, time_intervals, bitrate=DEFAULT_BITRATE):
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
            timeseries = Timeseries.from_time_and_channel_name(channel_name, time_intervals)
            missing_times = TimeIntervalSet()
            report = report_class.from_timeseries(self, timeseries) # TODO this is hacky, fix it

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
            report = report_class(bitrate=bitrate, time_intervals=time_intervals)
            report_anomalies_only = report
            report_sans_anomalies = report

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
        for r in self.report, self.report_anomalies_only, self.report_sans_anomalies:
            if not isinstance(r, self.get_report_class()):
                raise ValueError('key ' + r.__name__ + ' must be instance of ' + self.report_class_name)
            r._assert_self_consistent()
            # r._confirm_unionability(self.get_report_class()(self.bitrate))
            if self.bitrate != r.bitrate:
                raise ValueError('key ' + r.__name__ + ' has different bitrate than this ReportSet')
            if self.__version__ != r.__version__:
                raise ValueError('key ' + r.__name__ + ' has different version than this ReportSet')
        for t in self.time_intervals, self.missing_times:
            if not isinstance(t, TimeIntervalSet):
                raise ValueError('key ' + t.__name__ + ' must be instance of TimeIntervalSet')
            t._assert_self_consistent()
            if self.__version__ != t.__version__:
                raise ValueError('key ' + t.__name__ + ' has different version than this ReportSet')
        if self.report_anomalies_only + self.report_sans_anomalies != self.report:
            raise ValueError('whole report should be union of anomalous and nominal parts')
        if self.missing_times + self.time_intervals != self.time_intervals:
            raise ValueError('missing times should be subset of all times in ReportSet')
        if self.time_intervals != self.report.time_intervals:
            raise ValueError('time intervals in full Report and ReportSet should match')
        assert np.int64(self.bitrate) == self.bitrate, 'bitrate must be an integer'

    def _confirm_unionability(self, other):
        if type(self) != type(other):
            raise ValueError('instances of ReportSet must be of same type')
        if self.get_report_class() != other.get_report_class():
            raise ValueError('instances of ReportSet must have same Report class')
        if self.channel_name != other.channel_name:
            raise ValueError('instances of ReportSet must have same channel_name')
        if self.bitrate != other.bitrate:
            raise ValueError('instances of ReportSet must have same bitrate')
        if self.__version__ != other.__version__:
            raise ValueError('instances of ReportSet must have same version')
        if self.time_intervals.intersection(other.time_intervals) == TimeIntervalSet([]):
            raise ValueError('instances of ReportSet cannot cover overlapping time intervals')

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
            time_intervals          = TimeIntervalSet.__from_dict__(d['time_intervals']),
            report                  = cls.get_report_class(d['report_class_name']).__from_dict__(d['report']),
            report_anomalies_only   = cls.get_report_class(d['report_class_name']).__from_dict__(d['report_anomalies_only']),
            report_sans_anomalies   = cls.get_report_class(d['report_class_name']).__from_dict__(d['report_sans_anomalies']),
            missing_times           = TimeIntervalSet.__from_dict__(d['missing_times'])
        )

    def __to_dict__(self):
        return {
            'report_class_name':        self.report_class_name,
            'bitrate':                  np.int64(self.bitrate),
            'version':                  self.__version__,
            'channel_name':             self.channel_name,
            'time_intervals':           self.time_intervals.__to_dict__(),
            'report':                   self.report.__to_dict__(),
            'report_anomalies_only':    self.report_anomalies_only.__to_dict__(),
            'report_sans_anomalies':    self.report_sans_anomalies.__to_dict__(),
            'missing_times':            self.missing_times.__to_dict__()
        }

    def __eq__(self, other):
        try:
            self._assert_self_consistent()
            other._assert_self_consistent()
        except ValueError():
            return False
        if type(self) != type(other):
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

def run_unit_tests():
    print 'Testing class initializations.'
    Timeseries((16384,))
    TimeIntervalSet()
    Histogram()
    Statistics()

    # TODO: make a timeseries and then from there unit test everything else

    print 'Testing TimeIntervalSet arithmetic.'
    assert TimeIntervalSet([66,69]) + TimeIntervalSet([67,72]) == TimeIntervalSet([66,72]), "Union failing"
    assert TimeIntervalSet([66,69]) * TimeIntervalSet([67,72]) == TimeIntervalSet([67,69]), "Intersection failing"
    assert TimeIntervalSet([66,69]) + TimeIntervalSet([70,72]) == TimeIntervalSet([66,69,70,72]), "Union failing"
    assert TimeIntervalSet([66,73]) - TimeIntervalSet([67,72]) == TimeIntervalSet([66,67,72,73]), "Complement failing"
    assert TimeIntervalSet([66,73]) - TimeIntervalSet([66,73]) == TimeIntervalSet(), "Complement failing"
    # TODO: Add some more arithmetic assertions.

    print 'Testing TimeIntervalSet frame time rounding.'
    assert TimeIntervalSet([65,124]).round_to_frame_times() == TimeIntervalSet([64, 128]), "Rounding to frame times is failing"
    assert TimeIntervalSet([64,128]).round_to_frame_times() == TimeIntervalSet([64, 128]), "Rounding to frame times is failing"
    assert TimeIntervalSet([63,65,120,133]).round_to_frame_times() == TimeIntervalSet([0,192]), "Rounding to frame times is failing"

    print 'Testing TimeIntervalSet length calculation.'
    assert TimeIntervalSet([6400,6464]).combined_length() == 64, 'Time interval total length calculations are off'
    assert TimeIntervalSet([0,4,6400,6466]).combined_length() == 70, 'Time interval total length calculations are off'

    print 'Testing TimeIntervalSet splitting into frame files.'
    try:
        TimeIntervalSet([66,68]).split_into_frame_file_intervals()
        raise AssertionError('Should not be able to split a time interval not having round endpoints')
    except AssertionError:
        pass

    print 'HDF5 file saving capabilities now in doctest.'

    # TODO: Add in tests for creating time intervals from strings
    # TODO: Add in HDF5 save/load tests for all classes

    clean_up()
    print 'Unit tests passed!'

def clean_up():
    """
    Clean up side-effects after unit and integration tests have been run.
    """
    if os.path.exists('geco_statistics_test_hdf5_dict_example.hdf5'):
        os.remove('geco_statistics_test_hdf5_dict_example.hdf5')
