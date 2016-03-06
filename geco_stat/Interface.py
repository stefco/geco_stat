# -*- coding: utf-8 -*-

import os
import h5py             # >=2.5.0
import abc
import numpy as np      # >=1.10.4
from geco_stat._version import __version__, __release__
from geco_stat._constants import __default_bitrate__


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
        self.__save_dict_to_hdf5__(self.__to_dict__(), filename)

    @classmethod
    def load_hdf5(cls, filename):
        """Load an instance saved in an hdf5 file."""
        # TODO: Make this a ReportInterface-defined staticmethod that only
        # needs class information that is already provided in the saved
        # dictionary.
        return cls.__from_dict__(cls.__load_dict_from_hdf5__(filename))

    @classmethod
    def __save_dict_to_hdf5__(cls, dic, filename):
        """
        Save a dictionary whose contents are only strings, np.float64,
        np.int64, np.ndarray, and other dictionaries following this structure
        to an HDF5 file. These are the sorts of dictionaries that are meant
        to be produced by the ReportInterface__to_dict__() method. The saved
        dictionary can then be loaded using __load_dict_to_hdf5__(), and the
        contents of the loaded dictionary will be the same as those of the
        original.
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
        # argument type checking
        if not isinstance(dic, dict):
            raise ValueError("must provide a dictionary")
        if not isinstance(path, str):
            raise ValueError("path must be a string")
        if not isinstance(h5file, h5py._hl.files.File):
            raise ValueError("must be an open h5py file")
        # save items to the hdf5 file
        for key, item in dic.items():
            if not isinstance(key, str):
                raise ValueError("dict keys must be strings to save to hdf5")
            # save strings, numpy.int64, and numpy.float64 types
            if isinstance(item, (np.int64, np.float64, str)):
                h5file[path + key] = item
                if not h5file[path + key].value == item:
                    raise ValueError('The data representation in the HDF5 file '
                                     'does not match the original dict.')
            # save numpy arrays
            elif isinstance(item, np.ndarray):
                h5file[path + key] = item
                if not np.array_equal(h5file[path + key].value, item):
                    raise ValueError('The data representation in the HDF5 file '
                                     'does not match the original dict.')
            # save dictionaries
            elif isinstance(item, dict):
                cls.__recursively_save_dict_contents_to_group__(
                    h5file, path + key + '/', item)
            # other types cannot be saved and will result in an error
            else:
                raise ValueError('Cannot save %s type.' % type(item))

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
            return cls.__recursively_load_dict_contents_from_group__(h5file,
                                                                     '/')

    @classmethod
    def __recursively_load_dict_contents_from_group__(cls, h5file, path):
        """
        Load contents of an HDF5 group. If further groups are encountered,
        treat them like dicts and continue to load them recursively.
        """
        ans = {}
        for key, item in h5file[path].items():
            if isinstance(item, h5py._hl.dataset.Dataset):
                ans[key] = item.value
            elif isinstance(item, h5py._hl.group.Group):
                ans[key] = cls.__recursively_load_dict_contents_from_group__(
                    h5file, path + key + '/')
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
        assert l % self.bitrate == 0, ('Flattened timeseries length must be '
                                       'integer mult of bitrate.')
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
    def __from_dict__(cls, d):
        """
        Construct an instance of this class using a dictionary of the form
        output by self.__to_dict__. Should generally be a class method.
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
