Bibliography (Useful Links)
===========================

The following links have proved useful in creating, documenting, testing, and
deploying this package.

Anomaly and Outlier Detection
-----------------------------

* http://scikit-learn.org/stable/modules/outlier_detection.html

Documentation and Testing using Sphinx
--------------------------------------

* http://thomas-cokelaer.info/tutorials/sphinx/docstring_python.html
* https://docs.python.org/2/library/doctest.html
* http://www.sphinx-doc.org/en/stable/extensions.html
* http://www.sphinx-doc.org/en/stable/ext/doctest.html
* http://www.sphinx-doc.org/en/stable/ext/autosummary.html
* http://www.sphinx-doc.org/en/stable/ext/math.html

Distribution using PyPI and pip
-------------------------------

* https://hynek.me/articles/sharing-your-labor-of-love-pypi-quick-and-dirty/
* https://pypi.python.org/pypi?%3Aaction=list_classifiers
* https://python-packaging.readthedocs.org/en/latest/minimal.html
* Setting up a ``requirements.txt`` file that automatically gets required
  dependencies from the ``setup.py`` file: https://caremad.io/2013/07/setup-vs-requirement/
* A little bit more discussion of the ``setup.py`` ``install_requires``
  variable: https://packaging.python.org/en/latest/requirements/
* Including extra requirements for nonstandard usage:
  https://pythonhosted.org/setuptools/setuptools.html#declaring-extras-optional-features-with-their-own-dependencies

Running a function from the Command Line
----------------------------------------

* https://docs.python.org/2/tutorial/modules.html#executing-modules-as-scripts
* http://stackoverflow.com/questions/34952745/how-can-one-enable-a-shell-command-line-argument-for-a-python-package-installed
* How to make sure that only a single instance of your code is running:
  http://blog.tplus1.com/blog/2012/08/08/python-allow-only-one-running-instance-of-a-script/
* A stackoverflow question on the topic with some nice alternative approaches:
  http://stackoverflow.com/questions/380870/python-single-instance-of-program
* Documentation on ``sys.excepthook``, used to call cleanup code right before
  exiting when your program crashes: https://docs.python.org/2/library/sys.html

Using Read the Docs for Documentation
-------------------------------------

* https://read-the-docs.readthedocs.org/en/latest/getting_started.html
* Astropy is a very good (and thorough) example of advanced Read The Docs
  support in Python: https://github.com/astropy/astropy

Writing in Restructured Text (reST)
-----------------------------------

* I'm used to markdown, so this comparison of Restructured Text (reST) was very
  helpful: http://www.unexpected-vortices.com/doc-notes/markdown-and-rest-compared.html

Python
------

* A very good guide to python method decorators: https://julien.danjou.info/blog/2013/guide-python-static-class-abstract-methods
* Detailed description of ``super()``: https://rhettinger.wordpress.com/2011/05/26/super-considered-super/

Vim Fun
-------

* Negative regex matching: http://vim.wikia.com/wiki/Search_for_lines_not_containing_pattern_and_other_helpful_searches

Misc.
-----

* How to schedule jobs on UNIX systems using `chrontab`: http://kvz.io/blog/2007/07/29/schedule-tasks-on-linux-using-crontab/
* How to schedule larger cluster jobs using Condor: https://www.lsc-group.phys.uwm.edu/lscdatagrid/doc/condorview.html
* How to determine what OS you are running on: http://stackoverflow.com/questions/394230/detect-the-os-from-a-bash-script
* http://stackoverflow.com/questions/592620/check-if-a-program-exists-from-a-bash-script

