#!/usr/bin/env python

from setuptools import setup

setup(name='resource_alerter',
      version='0.0.0a1',
      description='monitors system resources and alerts users to high usage',
      classifiers=[
          'Development Status :: 2 - Pre-Alpha',
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
      url='https://github.com/Brazelton-Lab/bio_utils/',
      download_url='https://github.com/TheOneHyer/resource_alerter/tarball/'
                    + '0.0.0a1',
      author='Alex Hyer',
      author_email='theonehyer@gmail.com',
      license='GPLv3',
      packages=[
          'resource_alerter'
      ],
      include_package_data=True,
      zip_safe=False
      # install_requires=[]
      )