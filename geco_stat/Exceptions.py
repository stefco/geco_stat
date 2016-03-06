# -*- coding: utf-8 -*-


class VersionException(Exception):
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
