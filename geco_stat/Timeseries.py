# -*- coding: utf-8 -*-

import os
import subprocess
import numpy as np      # >=1.10.4
from geco_stat._constants import __default_bitrate__
from geco_stat.Exceptions import MissingChannelDataException
from geco_stat.Time import TimeIntervalSet


class Timeseries(np.ndarray):
    """
    A thin wrapper for ndarrays, adding in a couple of convenience methods
    used to create new instances from gravitational wave frame files.
    """

    @classmethod
    def from_time_and_channel_name(
        cls,
        channel_name,
        time_interval,
        bitrate=__default_bitrate__
    ):
        """
        Load a timeseries using this channel_name and time_interval.

        The time_interval argument must, at the moment, correspond to a single
        gravitational wave frame file. Future implementations might change this.
        """
        frame_path = cls.locate_frame_file(channel_name, time_interval)
        return cls.from_frame_file(
            channel_name,
            frame_path,
            time_interval,
            bitrate)

    @classmethod
    def from_frame_file(
        cls,
        channel_name,
        path,
        time_intervals,
        bitrate=__default_bitrate__
    ):
        """
        Load channel from file path to array.

        If a channel doesn't exist within the
        frame file located at the specified path, this function will return
        None. Otherwise, it returns an ndarray with one row for each second of
        data in the frame file.
        """

        # make sure path exists
        if not os.path.exists(path):
            raise ValueError('Path does not exist: ' + path)

        # set up the processes for acquiring and processing the data
        dump = subprocess.Popen(
            ["framecpp_dump_channel","--channel",channel_name,path],
            stdout=subprocess.PIPE)
        data_string = dump.communicate()[0]
        # print(now() + ' Timeseries retrieved, beginning processing.')

        # remove headers from the data
        formatted_data_string = cls.__remove_header_and_text__(data_string)

        # if the string is empty, the channel didn't exist. return None.
        if formatted_data_string == '':
            raise MissingChannelDataException()

        # instantiate numpy array and return it; will have number of rows equal
        # to the number of seconds in a frame file and number of columns equal
        # to the bitrate of the channel.
        ans = np.fromstring(formatted_data_string, sep=',').reshape(
            (64, bitrate)).view(cls)
        ans.time_intervals = time_intervals
        ans.bitrate = bitrate
        return ans

    def get_num_seconds(self):
        """
        Get the number of seconds worth of data in this frame file.
        """
        if self.shape[0] != self.time_intervals.combined_length():
            raise Exception('data corrupted; mismatch between time_interval '
                            'length and number of seconds of data')
        return self.shape[0]

    @staticmethod
    def locate_frame_file(channel_name, time_interval):
        """
        Find the gravitational wave frame file corresponding to a particular
        time interval for a particular channel name.
        """
        if time_interval.round_to_frame_times() != time_interval:
            raise ValueError('time interval must be rounded to frame times')
        if time_interval.combined_length() != 64:
            raise ValueError('time interval must fit a single frame file')
        if len(time_interval) != 2:
            raise ValueError('time interval set must be 1 continuous interval')
        if not isinstance(channel_name, str):
            raise ValueError('channel_name must be a string')
        if not isinstance(time_interval, TimeIntervalSet):
            raise ValueError('time_interval must be a TimeIntervalSet')

        detector_prefix = channel_name[0]
        dump = subprocess.Popen([
            'gw_data_find',
            '-o', detector_prefix,
            '-t', detector_prefix + '1_R',
            '-s', time_interval.to_ndarray()[0],
            '-e', time_interval.to_ndarray()[1],
            '-u', 'file'], stdout=subprocess.PIPE)
        frame_path = dump.communicate()[0]
        if frame_path[0:15] != 'file://localhost':
            raise Exception('expected file://localhost prefix output from ' +
                            'gw_data_find, got %s' % frame_path[0:15])
        frame_path = frame_path[16:]
        if not os.path.exists(frame_path):
            raise Exception('gw_data_find returned faulty ' +
                            'path:\n\t %s' % frame_path)
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

    @classmethod
    def __remove_header_and_text__(cls, string):
        """
        Delete first 6 lines; all spaces; and the word 'Data:' which precedes
        the numerical data.

        (This replaces sed and tr in the original implementation with native
        python.)
        """
        return cls.__remove_lines__(string, 6).translate(None, 'Dat: ')
