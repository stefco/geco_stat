## Deploying to PyPI

`setup.py` should be configured properly. Make sure to update the `RELEASE`
variable to reflect whatever little changes you've introduced (though `VERSION`
can remain unchanged if it is a minor change preserving backwards compatibility,
like a bug fix). Next, run

    python setup.py sdist
    python setup.py bdist_wheel
    twine upload dist/*
