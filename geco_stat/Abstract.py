# -*- coding: utf-8 -*-

import os
import h5py             # >=2.5.0
import abc
import numpy as np      # >=1.10.4
from geco_stat._version import __version__
from geco_stat._constants import __default_bitrate__

# TODO: Implement.
class AbstractTimeIntervalSet(object):
    """
    The AbstractTimeIntervalSet defines what objects can specify time intervals
    over which data might be collected. In practice, it should only have one
    implementation; the abstract class serves mainly to keep the type graph
    acyclic and restrictive.
    """
    __metaclass__  = abc.ABCMeta
    __version__ = __version__

# TODO: Implement.
class AbstractTimeSeries(object):
    """
    The AbstractTimeSeries provides a way of defining the category of objects
    which can serve as valid sources of information for geco_stat. In
    practice, it should only have one implementation; the abstract class serves
    mainly to keep the type graph acyclic.
    """
    __metaclass__  = abc.ABCMeta
    __version__ = __version__

class AbstractTimeSeriesDerivable(object):
    """
    The purpose of ``geco_stat`` is to look at data and do things with it,
    so it is fitting that the primordial interface provides methods for
    creating a new instance using a Timeseries.
    """
    __metaclass__  = abc.ABCMeta
    __version__ = __version__

    @abc.abstractmethod
    def clone(self):
        """
        Create and return a new instance of this class which shares all
        values (and which would return true in an equality test) with this
        instance, but which shares no object pointers (even in sub-properties)
        and can hence be modified with impunity without fear of side-effects.
        """

    def get_times(self):
        """
        Get an AbstractTimeIntervalSet instance representing the time intervals
        covered by this instance.
        """
        # If storing times differently than suggested here, implement a
        # different method. But using ``_times`` seems reasonable.
        if isinstance(self, AbstractTimeIntervalSet):
            return self.clone()
        elif isinstance(self._times, AbstractTimeIntervalSet):
            return self._times.clone()

    @classmethod
    @abc.abstractmethod
    def from_timeseries(cls, timeseries):
        """
        Create a compatible object using an AbstractTimeSeries as input.
        """

class AbstractNonIntersectingUnionable(AbstractTimeSeriesDerivable):
    """
    An interface describing classes whose members contain information that is
    associated with specific time intervals. These members can be unioned or
    "added" together provided that they don't contain redundant time
    information. This makes it possible to iteratively build instances of
    AbstractNonIntersectingUnionable that cover large, possibly disjoint
    spans of time from smaller "atomic" instances simply by unioning.
    """
    __metaclass__  = abc.ABCMeta
    __version__ = __version__

    # FIXME: This is a hack. This should be an abstract class, but most
    # subclasses have implemented the private methods, so this is a temporary
    # kludge.
    def union(self, other):
        """
        Combine these two instances to cover a larger span of time. Like the
        ``clone`` method, this should return an instance sharing no object
        pointers with the original instances.
        """
        return self.__union__(other)

    # There is no reason to check for consistency every time; too much
    # abstraction with no clarifying purpose.
    # FIXME deprecated
    @abc.abstractmethod
    def __union__(self, other):
        """
        Aggregate these two instances without first checking that the instances
        are compatible or self-consistent. This is part of the implementation
        of the union method.
        """


    @abc.abstractmethod
    def __eq__(self, other):
        """
        Instances must have a way of determining equality that is based on
        values rather than ids, i.e. if the contents of two instances contain
        the same information, then they are equal, regardless of whether
        they are the same instance in memory.
        """

    def __ne__(self, other):
        return not self == other


    def __add__(self, other):
        """
        Addition is a shorthand for union.
        """
        return self.union(other)

    # TODO Decide what to do about these consistency checks. Maybe implement
    # a very simple top-level check that can be overridden or extended as
    # needed, but only if it is considered important; this should not distract.
    # In any case, the private method name is undesirable and should be
    # replaced with something better. Not deprecated -- for now.
    # ALMOST deprecated...
    @abc.abstractmethod
    def _assert_self_consistent(self):
        """
        Make sure this instance is self-consistent.
        """

class AbstractDictRepresentable(AbstractNonIntersectingUnionable):
    """
    Subclasses of AbstractDictRepresentable contain information that can be
    represented as a **PARTICULAR** type of dictionary. To be specific, they
    can be represented as dictionaries whose elements are one of:

    1. A string.
    2. A numpy.int64.
    3. A numpy.float64.
    4. A numpy.ndarray.
    5. A AbstractDictRepresentable instance.

    This allows for unambiguous file saving and loading through the uniform
    intermediate step of a dictionary representation.
    """
    __metaclass__  = abc.ABCMeta
    __version__ = __version__

    # FIXME: This is a hack. This should be an abstract class, but most
    # subclasses have implemented the private methods, so this is a temporary
    # kludge.
    def to_dict(self):
        """
        Return a dictionary whose elements consist of strings, ints, lists, or
        numpy.ndarray objects, or of other dicts whose contents follow this
        pattern recursively. This dictionary must wholly represent the data in
        this object, so that this object may be totally reconstructed using
        the dictionary's contents. This is an implementation method used to
        store data in HDF5.
        """
        return self.__to_dict__()

    # FIXME: This is a hack. This should be an abstract class, but most
    # subclasses have implemented the private methods, so this is a temporary
    # kludge.
    def from_dict(cls, d):
        """
        Construct an instance of this class using a dictionary of the form
        output by self.__to_dict__. Should generally be a class method.
        """
        return cls.__from_dict__t(d)

    def clone(self):
        """
        Create and return a new instance of this class which shares all
        values (and which would return true in an equality test) with this
        instance, but which shares no object pointers (even in sub-properties)
        and can hence be modified with impunity without fear of side-effects.
        """
        # If this implementation makes you nervous (for anything besides
        # performance reasons, then you are not properly implementing the
        # to_dict and from_dict methods.
        return self.__from_dict__(self.__to_dict__())

    # This interface should become "to_dict", since it will likely be
    # useful for users.
    # FIXME deprecated
    @abc.abstractmethod
    def __to_dict__(self):
        pass

    # This interface should become "from_dict", since it will likely be
    # useful for users.
    # FIXME deprecated
    @abc.abstractmethod
    def __from_dict__(cls, d):
        pass

class HDF5_IO(AbstractDictRepresentable):
    """
    Uses the ``to_dict`` methods of AbstractDictRepresentable to save and load
    HDF5 files of arbitrary complexity.
    """
    __metaclass__  = abc.ABCMeta
    __version__ = __version__

    def save_hdf5(self, filename):
        """Save this instance to an hdf5 file."""
        self.__save_dict_to_hdf5__(self.__to_dict__(), filename)

    @classmethod
    def load_hdf5(cls, filename):
        """Load an instance saved in an hdf5 file."""
        # TODO: Make this a AbstractReport-defined staticmethod that only
        # needs class information that is already provided in the saved
        # dictionary.
        return cls.__from_dict__(cls.__load_dict_from_hdf5__(filename))

    @classmethod
    def __save_dict_to_hdf5__(cls, dic, filename):
        """
        Save a dictionary whose contents are only strings, np.float64,
        np.int64, np.ndarray, and other dictionaries following this structure
        to an HDF5 file. These are the sorts of dictionaries that are meant
        to be produced by the AbstractReport__to_dict__() method. The saved
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
        AbstractReport subclass instances using the
        AbstractReport.__from_dict__() method.
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

# Rename AbstractReport; it should be called something more
# usage-agnostic and feature-descriptive.
# FIXME deprecated
class AbstractReport(HDF5_IO):
    "Abstract interface used by all geco_statistics classes"
    __metaclass__  = abc.ABCMeta
    __version__ = __version__

    # This should be handled through ducktyping.
    # FIXME deprecated
    @abc.abstractmethod
    def _confirm_unionability(self, other):
        "Make sure these two instances can be unioned."

