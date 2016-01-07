#! /usr/bin/env python

"""Setup utility for resource_alerterd

Usage:

    resource_alerted_setup.py [--force-yes]

Synopsis:

    This script simply creates the log folder and process ID folder required to
    run resource_alerted. --force-yes just answers yes to all questions
    asked by this script.

Import Notes:

    1) This process should be run with root permissions to function properly

    2) Run this script before starting this daemon for the first time
"""

from __future__ import print_function
import argparse
import os
import sys

__author__ = 'Alex Hyer'
__email__ = 'theonehyer@gmail.com'
__license__ = 'GPLv3'
__maintainer__ = 'Alex Hyer'
__status__ = 'Development'
__version__ = '0.0.0b2'


class InputError(Exception):
    pass


def robust_input(message):
    """Provide proper input function based on Python version

    :param message: Message to display to user
    :type message: str

    :return: function based on Python version
    :rtype: function
    """

    major_version = sys.version_info[0]
    if major_version == 3:
        return input(message)
    else:
        return raw_input(message)


def yes_no(answer):
    """Provide semi-robust analysis of user answers

    :param answer: String given by user
    :type answer: str

    :return: True or False based on answer
    :rtype: bool
    """

    global valid
    valid = {
        'yes': True,
        'ye': True,
        'y': True,
        'no': False,
        'n': False
    }

    answer = answer.lower()
    if answer in valid:
        return valid[answer]
    else:
        # This message should only show up if I didn't write a catch for input
        print('Answer {0} is not valid: this message is the result of a bug, '
              'please email theonehyer@gmail.com concerning this error')
        sys.exit(1)


def main(args):
    # Test if runtime folder exists and, if it does not, try to create it
    runtime_folder = '/var/run/resource_alerterd'
    if not os.path.isfile(runtime_folder):
        if args.force_yes:
            create = True
        else:
            print('Your system does not have the following folder: {0}\n'
                  'This folder is required and stores important runtime '
                  'data.')
            message = 'Create {0} [yes/no]: '.format(runtime_folder)
            while True:
                try:
                    answer = robust_input(message)
                    if answer not in valid:
                        raise InputError
                    else:
                        break
                except InputError:
                    print('{0} is not "yes" or "no". Please try '
                          'again.'.format(answer))
            create = yes_no(answer)
        if create:
            os.mkdir(runtime_folder)
            print('{0} successfully created'.format(runtime_folder))

    # Test if logging folder exists and, if it does not, try to create it
    logging_folder = '/var/log/resource_alerter'
    if not os.path.isfile(logging_folder):
        if args.force_yes:
            create = True
        else:
            print('Your system does not have the following folder: {0}\n'
                  'This folder is required and is where data is logged.')
            message = 'Create {0} [yes/no]: '.format(logging_folder)
            while True:
                try:
                    answer = robust_input(message)
                    if answer not in valid:
                        raise InputError
                    else:
                        break
                except InputError:
                    print('{0} is not "yes" or "no". Please try '
                          'again.'.format(answer))
            create = yes_no(answer)
        if create:
            os.mkdir(logging_folder)
            print('{0} successfully created'.format(logging_folder))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.
                                     RawDescriptionHelpFormatter)
    parser.add_argument('-f', '--force_yes',
                        action='store_true',
                        help='answer yes to all questions w/o asking user')
    args = parser.parse_args()

    main(args)
    sys.exit(0)
