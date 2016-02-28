#!/usr/bin/env python
import os
from setuptools import setup, find_packages


long_description = open(
    os.path.join(
        os.path.dirname(__file__),
        'README.md'
    )
).read()


setup(
    name='puppyjustice',
    author='Adam Schwalm',
    version='0.1',
    license='LICENSE',
    description='Automatically generate PuppyJustice videos',
    long_description=long_description,
    packages=find_packages('.', exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    install_requires=["docopt", "google-api-python-client"],
    keywords=[]
)
