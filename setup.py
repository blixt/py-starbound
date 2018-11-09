#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import find_packages, setup
from starbound import __version__


def readme():
    with open('README.md') as f:
        return f.read()


setup(
    name='py-starbound',
    version=__version__,
    packages=find_packages(),
    include_package_data=True,
    license='MIT License',
    description='Python package for working with Starbound files.',
    long_description=readme(),
    long_description_content_type='text/markdown',
    url='https://github.com/blixt/py-starbound',
    author='Blixt',
    author_email='me@blixt.nyc',
    # Shouldn't have any deps other than Python itself
        install_requires=[
    ],
    # https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
            'Development Status :: 5 - Production/Stable',
            'Environment :: Console',
            'Intended Audience :: Developers',
            'Intended Audience :: End Users/Desktop',
            'License :: OSI Approved :: MIT License',
            'Natural Language :: English',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 3',
            'Topic :: Games/Entertainment',
            'Topic :: Utilities',
    ],
    entry_points={
            'console_scripts': [
                'pystarbound-region = starbound.cliregion:main',
                'pystarbound-repair = starbound.clirepair:main',
                'pystarbound-export = starbound.cliexport:main',
            ],
    },
)
