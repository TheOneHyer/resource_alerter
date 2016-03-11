#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='resource_alerter',
      version='0.0.1rc1',
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
                    + '0.0.1rc1',
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
          'resource_alerter/resource_alerterd_setup.py',
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
