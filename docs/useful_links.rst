Bibliography (Useful Links)
===========================

The following links have proved useful in creating, documenting, testing, and
deploying this package.

Anomaly and Outlier Detection
-----------------------------

* Some strategies for `outlier and anomaly detection`_ (and a good
  explanation of the differences between the two).

.. _outlier and anomaly detection: http://scikit-learn.org/stable/modules/outlier_detection.html

Packaging and Distribution using PyPI and pip
---------------------------------------------

* `How to structure the directories in your python package`_.
* `How to give everything in your project the same version and release numbers`_,
  from Read The Docs documentation (via Sphinx) to the module API and the PyPI
  distribution version.
* `Quick and dirty intro`_ to PyPI.
* `Comprehensive list`_ of ``list_classifiers`` used to describe your package.
* `Official guide`_ to getting started with PyPI packaging and distribution.
* `Setting up`_ a ``requirements.txt`` file that automatically gets required
  dependencies from the ``setup.py`` file.
* `More discussion`_ of the ``setup.py`` ``install_requires`` variable.
* `Including extra requirements for nonstandard usage`_.
* `Adding`_ a ``publish`` and autoversion feature to ``setup.py``.

.. _How to structure the directories in your python package: http://stackoverflow.com/questions/17457782/how-to-structure-python-packages-without-repeating-top-level-name-for-import/17530651#17530651
.. _How to give everything in your project the same version and release numbers: https://packaging.python.org/en/latest/single_source_version/
.. _Comprehensive list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
.. _Quick and dirty intro: https://hynek.me/articles/sharing-your-labor-of-love-pypi-quick-and-dirty/
.. _Official guide: https://python-packaging.readthedocs.org/en/latest/minimal.html
.. _Setting up: https://caremad.io/2013/07/setup-vs-requirement/
.. _More discussion: https://packaging.python.org/en/latest/requirements/
.. _Including extra requirements for nonstandard usage: https://pythonhosted.org/setuptools/setuptools.html#declaring-extras-optional-features-with-their-own-dependencies
.. _Adding: http://www.pydanny.com/python-dot-py-tricks.html

Running a Python Script from the Command Line
---------------------------------------------

* `Simple execution of a module as a script`_ (not from a package, but in the
  current directory).
* Quick explanation of `how to use entry points`_ to accomplish this in a package.
* `How to make sure that only a single instance of your code is running`_.
* `A stackoverflow question on the topic with some nice alternative approaches`_.
* Documentation on ``sys.excepthook``,
  `used to call cleanup code right before exiting when your program crashes`_.

.. _Simple execution of a module as a script: https://docs.python.org/2/tutorial/modules.html#executing-modules-as-scripts
.. _how to use entry points: http://stackoverflow.com/questions/34952745/how-can-one-enable-a-shell-command-line-argument-for-a-python-package-installed
.. _How to make sure that only a single instance of your code is running: http://blog.tplus1.com/blog/2012/08/08/python-allow-only-one-running-instance-of-a-script/
.. _A stackoverflow question on the topic with some nice alternative approaches: http://stackoverflow.com/questions/380870/python-single-instance-of-program
.. _used to call cleanup code right before exiting when your program crashes: https://docs.python.org/2/library/sys.html

Using Read the Docs for Documentation
-------------------------------------

* `Official getting started guide`_.
* `Astropy`_ is a very good (and thorough) example of advanced Read The Docs
  support in Python.
* `Official solution`_ regarding how to fix Read the Docs build failures resulting
  from hard c dependencies (like h5py requiring HDF5).
* `Example`_ of the above.
* `Using the official Read the Docs Theme`_ in your homemade documentation.

.. _Official solution: http://read-the-docs.readthedocs.org/en/latest/faq.html#i-get-import-errors-on-libraries-that-depend-on-c-modules
.. _Official getting started guide: https://read-the-docs.readthedocs.org/en/latest/getting_started.html
.. _Astropy: https://github.com/astropy/astropy
.. _Example: https://github.com/astropy/halotools/issues/154
.. _Using the official Read the Docs Theme: https://github.com/snide/sphinx_rtd_theme

Writing in Restructured Text (reST)
-----------------------------------

* I'm used to markdown, so `this comparison`_ of Restructured Text (reST) was
  very helpful.

.. _this comparison: http://www.unexpected-vortices.com/doc-notes/markdown-and-rest-compared.html

Python
------

* A `very good guide`_ to python method decorators.
* `Detailed description`_ of ``super()``.

.. _very good guide: https://julien.danjou.info/blog/2013/guide-python-static-class-abstract-methods
.. _Detailed description: https://rhettinger.wordpress.com/2011/05/26/super-considered-super/

Python on Travis CI:
--------------------

* `Getting started`_ with ``.travis.yml`` for python.
* `Deploying to PyPI`_ using Travis.
* Fix build failures due to `missing HDF5 dependency`_ (a good hint that this
  is the problem you are facing is a missing ``hdf5.h`` header file warning in your
  logfile).
* Using `system site packages`_ (the ``system_site_packages`` option in
  ``.travis.yml``) to use the ``apt`` versions of python (NOTE:
  you *should not* do this for any packages that need to be tested on many
  versions of Python, since generally only one or two versions will be available
  via ``apt``. See the next link for details.).
* Why ``system_site_packages`` `breaks multi-version tests`_.
* `More info`_ on the ``system_site_packages`` option breaks multi-version tests,
  **plus** a very good example of how to test system site package versions of
  python *without* flagging this option, using the syntax:

  ::

      - "pypy"
      - 2.7
      - "2.7_with_system_site_packages"

  (inclusion of other versions follows the same pattern).
* Test `special requirements`_ for each python version.

.. _Getting started: https://docs.travis-ci.com/user/languages/python
.. _Deploying to PyPI: https://docs.travis-ci.com/user/deployment/pypi
.. _missing HDF5 dependency: http://askubuntu.com/questions/630716/cannot-install-libhdf5-dev
.. _system site packages: https://groups.google.com/forum/#!topic/travis-ci/cdJajrAWcKs
.. _breaks multi-version tests: https://github.com/travis-ci/travis-ci/issues/4260
.. _More info: https://github.com/travis-ci/travis-ci/issues/2219#issuecomment-41804942
.. _special requirements: http://stackoverflow.com/questions/20617600/travis-special-requirements-for-each-python-version

Vim Fun
-------

* `Negative regex matching`_.
* `Running python code from within vim`_.
* `Saving vim macros`_.
* `Put backspace in a vim macro`_ (make sure to use double-quotes).

.. _Negative regex matching: http://vim.wikia.com/wiki/Search_for_lines_not_containing_pattern_and_other_helpful_searches
.. _Running python code from within vim: http://stackoverflow.com/questions/18948491/running-python-code-in-vim
.. _Saving vim macros: http://stackoverflow.com/questions/2024443/saving-vim-macros
.. _Put backspace in a vim macro: http://stackoverflow.com/questions/27578758/vim-macro-with-backspace

Git Tricks
----------

* Use `git show`_ to ``cat`` the contents of an old revision of a file.
* `See the differences`_ in a particular file between revisions.
* `Tag your commits`_ with, e.g., version information
* Add `hooks`_ to your commits so that ``git`` automatically performs certain
  tasks before/after operations like ``git commit``. Useful for, e.g.,
  auto-tagging commits when the version updates!
* Symbolic link to hooks in git, for `version-controlling your git hooks`_.

.. _git show: http://stackoverflow.com/questions/888414/git-checkout-older-revision-of-a-file-under-a-new-name
.. _See the differences: http://stackoverflow.com/questions/3338126/how-to-diff-the-same-file-between-two-different-commits-on-the-same-branch
.. _Tag your commits: https://git-scm.com/book/en/v2/Git-Basics-Tagging
.. _hooks: https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks
.. _version-controlling your git hooks: http://stackoverflow.com/questions/4592838/symbolic-link-to-a-hook-in-git

Python Versions
---------------

* ``execfile`` no longer exists in Python3.x; `replace it with this`_.
* ``/`` always returns a float in Python3.x; use ``//`` for `integer division`_ in
  any version of Python.

.. _integer division: http://stackoverflow.com/questions/15173715/why-is-there-a-typeerror
.. _replace it with this: http://stackoverflow.com/questions/6357361/alternative-to-execfile-in-python-3

Documentation and Testing using Sphinx
--------------------------------------

* http://thomas-cokelaer.info/tutorials/sphinx/docstring_python.html
* https://docs.python.org/2/library/doctest.html
* http://www.sphinx-doc.org/en/stable/extensions.html
* http://www.sphinx-doc.org/en/stable/ext/doctest.html
* http://www.sphinx-doc.org/en/stable/ext/autosummary.html
* http://www.sphinx-doc.org/en/stable/ext/math.html

Misc.
-----

* How to `schedule jobs`_ on UNIX systems using ``chrontab``.
* How to `schedule larger cluster jobs`_ using Condor.
* How to `determine what OS you are running on`_.
* How to `check if a program or command exists`_ from within a bash script.

.. _schedule jobs: http://kvz.io/blog/2007/07/29/schedule-tasks-on-linux-using-crontab/
.. _schedule larger cluster jobs: https://www.lsc-group.phys.uwm.edu/lscdatagrid/doc/condorview.html
.. _determine what OS you are running on: http://stackoverflow.com/questions/394230/detect-the-os-from-a-bash-script
.. _check if a program or command exists: http://stackoverflow.com/questions/592620/check-if-a-program-exists-from-a-bash-script

