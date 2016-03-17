# -*- coding: utf-8 -*-

import os
import h5py             # >=2.5.0
import abc
import numpy as np      # >=1.10.4
from geco_stat._version import __version__
from geco_stat._constants import __default_bitrate__
from geco_stat.Exceptions import VersionException

# You can store classes in the factory for later recovery, but you have to
# manually add classes to the factory after defining them.
class Factory(object):
    """
    A factory class for mapping the names of AbstractDictRepresentable subclass
    names to their corresponding subclasses. Classes can be added to the
    factory using the ``add_class`` method and recovered using the
    ``get_class`` method, which is useful for, e.g., reconstructing an object
    from a dictionary when the class of that object is specified as a string.

    For example, if ``d`` is such a dictionary, then

        cls = geco_stat.Factory.get_class(d['class'])

    can be used to get (what is presumably) the original class associated with
    the instance represented by that dictionary. The rest of the data in that
    dictionary should then be sufficient (along with the class itself) to
    reconstruct the original object. At the time of writing, this is the
    approach favored by the ``__from_dict__`` private methods used by
    ``from_dict``.

    You can store classes in the factory for later recovery, but you have to
    manually add classes to the factory after defining them. This approach has
    the advantage of facilitating runtime modifications for prototyping or
    advanced munging/scripting purposes; simply defining a new class and
    adding it to the factory should be enough to give it all of the features of
    built-in geco_stat classes.
    """

    _factory = dict()

    @staticmethod
    def add_class(newcls, name=None):
        """
        Store a class in the factory for later retrieval.

        >>> geco_stat.Factory.add_class(object, 'object')
        """
        if name is None:
            name = newcls.__name__
        Factory._factory[name] = newcls 

    @staticmethod
    def get_class(clsname):
        """
        Retrieve a class by name:

        >>> geco_stat.Factory.get_class('object')
        object
        """
        return Factory._factory[clsname]

    @staticmethod
    def classes():
        """
        List all classes currently in the factory.

        >>> geco_stat.Factory.classes()
        [object]
        """
        return Factory._factory.values()

    @staticmethod
    def classnames():
        """
        List the names of all classes currently in the factory.

        >>> geco_stat.Factory.classnames()
        ['object']
        """
        return Factory._factory.keys()

    @staticmethod
    def items():
        """
        Return a list of key-value pair tuples containing the names
        and classes for each class stored in the factory.

        >>> geco_stat.Factory.items()
        [('object', object)]
        """
        return Factory._factory.items()

    @staticmethod
    def del_class(clsname):
        """
        Remove a class from the factory.

        >>> geco_stat.Factory.del_class('object')
        """
        del Factory._factory[clsname]

class AbstTimeIntervals(object):
    """
    The AbstTimeIntervals defines what objects can specify time intervals
    over which data might be collected. In practice, it should only have one
    implementation; the abstract class serves mainly to keep the type graph
    acyclic and restrictive.

    This abstract class is meant for organizational/conceptual purposes and
    does not specify an interface or implement any methods.
    """
    __metaclass__  = abc.ABCMeta
    __version__ = __version__

class AbstractTimeSeries(object):
    """
    The AbstractTimeSeries provides a way of defining the category of objects
    which can serve as valid sources of information for geco_stat. In
    practice, it should only have one implementation; the abstract class serves
    mainly to keep the type graph acyclic.

    This abstract class is meant for organizational/conceptual purposes and
    does not specify an interface or implement any methods.
    """
    __metaclass__  = abc.ABCMeta
    __version__ = __version__

class AbstTimeSeriesDerivable(object):
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
        Get an AbstTimeIntervals instance representing the time intervals
        covered by this instance.
        """
        # If storing times differently than suggested here, implement a
        # different method. But using ``_times`` seems reasonable.
        if isinstance(self, AbstTimeIntervals):
            return self.clone()
        elif isinstance(self._times, AbstTimeIntervals):
            return self._times.clone()

    @classmethod
    @abc.abstractmethod
    def from_timeseries(cls, timeseries):
        """
        Create a compatible object using an AbstractTimeSeries as input.
        """

class AbstUnionable(AbstTimeSeriesDerivable):
    """
    An interface describing classes whose members contain information that is
    associated with specific time intervals. These members can be unioned or
    "added" together provided that they don't contain redundant time
    information, i.e., provided their time interval sets are non-intersecting.
    This makes it possible to iteratively build instances of AbstUnionable that
    cover large, possibly disjoint spans of time from smaller "atomic"
    instances simply by unioning.
    """
    __metaclass__  = abc.ABCMeta
    __version__ = __version__

    # Use a template method approach to always make sure that these items
    # are unionable before proceeding.
    def union(self, other):
        """
        Combine these two instances to cover a larger span of time. Like the
        ``clone`` method, this should return an instance sharing no object
        pointers with the original instances.
        """
        self.assert_self_consistent()
        other.assert_self_consistent()
        self.assert_unionable(other)
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

    # TODO The private method name is undesirable and should be
    # replaced with something better. Not deprecated -- for now.
    @abc.abstractmethod
    def assert_self_consistent(self):
        """
        Make sure this instance is self-consistent.
        """

    @abc.abstractmethod
    def assert_unionable(self, other):
        """
        Make sure these two instances can be unioned.
        """

class AbstractDictRepresentable(object):
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

    def to_dict(self):
        """
        Return a dictionary whose elements consist of strings, ints, lists, or
        numpy.ndarray objects, or of other dicts whose contents follow this
        pattern recursively. This dictionary must wholly represent the data in
        this object, so that this object may be totally reconstructed using
        the dictionary's contents. This is an implementation method used to
        store data in HDF5.
        """
        # Unless overridden, this method will always check version and class
        # information, with class-specific treatment of the dictionary being
        # handled by a template method, __to_dict__.
        d = self.__to_dict__()
        d['version'] = self.__version__
        d['class'] = type(self).__name__
        return d

    @staticmethod
    def from_dict(d):
        """
        Construct an instance of this class using a dictionary of the form
        output by self.to_dict. Should generally be a class method.
        """
        # Unless overridden, this method will always check version and class
        # information, with class-specific treatment of the dictionary being
        # handled by a template method, __from_dict__.
        cls = Factory.get_class(d['class'])
        if d['version'] != cls.__version__:
            raise VersionException("Tried constructing an instance of %s "
                                   "using old version %s"
                                   % (cls.__name__, d['version']))
        return cls.__from_dict__(d)

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
        return self.from_dict(self.to_dict())

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

    # MUST BE A CLASS METHOD.
    @abc.abstractmethod
    def __from_dict__(cls, d):
        """
        Construct an instance of this class using a dictionary of the form
        output by self.to_dict. Should generally be a class method.
        """

class HDF5_IO(AbstractDictRepresentable):
    """
    Uses the ``to_dict`` methods of AbstractDictRepresentable to save and load
    HDF5 files of arbitrary complexity.
    """
    __metaclass__  = abc.ABCMeta
    __version__ = __version__

    def save_hdf5(self, filename):
        """Save this instance to an hdf5 file."""
        self.__save_dict_to_hdf5__(self.to_dict(), filename)

    @classmethod
    def load_hdf5(cls, filename):
        """Load an instance saved in an hdf5 file."""
        # TODO: Make this a AbstReport-defined staticmethod that only
        # needs class information that is already provided in the saved
        # dictionary.
        return cls.from_dict(cls.__load_dict_from_hdf5__(filename))

    @classmethod
    def __save_dict_to_hdf5__(cls, dic, filename):
        """
        Save a dictionary whose contents are only strings, np.float64,
        np.int64, np.ndarray, and other dictionaries following this structure
        to an HDF5 file. These are the sorts of dictionaries that are meant
        to be produced by the AbstractDictRepresentable.to_dict() method. The saved
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
        AbstractDictRepresentable subclass instances using the
        AbstractDictRepresentable.from_dict() method.
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

class AbstractPlottable(object):
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
        Create some sort of verbose, human-readable text summary for the
        information content of this object. Should return a string.
        """

