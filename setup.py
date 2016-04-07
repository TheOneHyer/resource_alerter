#!/usr/bin/env python

"""Installs resource_alerter package

Copyright:

    setup.py installs resource_alerter package
    Copyright (C) 2016  Alex Hyer

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from setuptools import setup, find_packages

setup(name='resource_alerter',
      version='0.0.1rc5',
      description='monitors system resources and alerts users to high usage',
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: No Input/Output (Daemon)',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
          'Natural Language :: English',
          'Operating System :: Unix',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3.4',
          'Topic :: System :: Logging',
          'Topic :: System :: Monitoring'
      ],
      keywords='daemon resource alerter monitor monitoring log logging',
      url='https://github.com/TheOneHyer/resource_alerter',
      download_url='https://github.com/TheOneHyer/resource_alerter/tarball/'
                    + '0.0.1rc5',
      author='Alex Hyer',
      author_email='theonehyer@gmail.com',
      license='GPLv3',
      packages=find_packages(),
      package_data={
          'resource_alerter': ['*.conf']
      },
      include_package_data=True,
      zip_safe=False,
      scripts=[
          'resource_alerter/resource_alerterd.py'
      ],
      install_requires=[
          'docutils',
          'lockfile >=0.10',
          'psutil',
          'pyyaml',
          'setuptools'
      ]
      )
