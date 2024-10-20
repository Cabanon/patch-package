# patch-package

![PyPI - Python Version](https://img.shields.io/pypi/pyversions/patch-package)
![PyPI](https://img.shields.io/pypi/v/patch-package)

**patch-package** is a Python library to automatically create and apply patches from changes made in installed packages. It is heavily inspired by [patch-package](https://github.com/ds300/patch-package) which is the equivalent for Node packages.

## Features

* Compatible with Python 2.7 and Python 3.5+
* Automatic code change detection between installed package and package source from pip
* Prevent patching when version or code are mismatching
* Automatic matching between import names and package names (e.g. yaml -> PyYAML) and fuzzy matching (e.g. request -> requests)

## Usage

Install the library from PyPI

    pip install patch-package

Make a change in one of your installed package and then generate the corresponding patch
    
    patch-package <package-name>

Then when reinstalling the package you can apply back your patches
    
    patch-package

All patches are contained in the *patches/* folder so it can be commited to git and reapply whenever you want

