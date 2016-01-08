#! /usr/bin/env python

"""Monitors CPU, RAM, and IO Wait and warns of/broadcasts high usage

Usage:

    resource_alerterd.py {start | stop | restart}

Synopsis:

    resource_alerterd is a Python daemon designed for Unix-like systems. As
    the name, it monitors system resource usage and alerts users to high
    resource usage. Specifically, resource_alerterd monitors CPU, RAM, and IO
    usage and logs use above specified percentage thresholds. Many aspects
    of the alerting algorithm are customizable in the configuration file.
    See README.md for more details.

Important Notes:

    1) This process should be run with root permissions to function properly

    2) Run resource_alerterd_setup.py before starting this daemon for the
       first time

Copyright:

    resource_alerted.py monitor resource usage and notifies users of high use
    Copyright (C) 2015  Alex Hyer

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

from resource_alerter.daemon import runner
import difflib
import logging
import logging.config
import os
from pkg_resources import resource_stream
import psutil
import shutil
import subprocess
import sys
import time
import yaml

__author__ = 'Alex Hyer'
__email__ = 'theonehyer@gmail.com'
__license__ = 'GPLv3'
__maintainer__ = 'Alex Hyer'
__status__ = 'Development'
__version__ = '0.0.0b6'


class ResourceAlerter:
    """Daemon-ized, checks various resource usage and alerts users

    This class is, for most intents and purposes, the actual run time process
    of resource_alerterd. In brief, this class monitors CPU, RAM, and IO
    usage and then alerts users to high usage of these resources.

    Function Summaries
    ------------------

    __init__: initializes run-time variables

    is_stable: static, determine if a given resource usage is stable

    non_kernel_pids: static, filter out kernel PIDs from a PID list

    wall: static, script and broadcast resource usage alert via 'wall'

    check_wall: determine if daemon can use 'wall'

    cpu_check: check CPU usage and log/broadcast high usage

    io_check: check IO usage and log/broadcast high usage

    pids_same_test: determine if PIDs have changed since last resource check

    ram_check: check RAM usage and log/broadcast high usage

    run: main loop of daemon, calls other functions listed here

    sleep_time: determine how long daemon should sleep between resource checks
    """

    def __init__(self, config):
        """Initializes many essential daemon-wide runt-time variables

        :param config: configuration file as dictionary
        :type: dict

        :return: nothing
        :rtype: N/A
        """

        self.config = config  # Dictionary from YAML configuration file
        self.io_max = None  # System dependent max IO percentage
        self.last_cpu_check = None
        self.last_cpu_override = None
        self.last_io_check = None
        self.last_io_override = None
        self.last_ram_check = None
        self.last_ram_override = None
        self.pidfile_path = '/var/run/resource_alerterd/resource_alerterd.pid'
        self.pidfile_timeout = 5
        self.pids_same = False  # True if PIDs since last check highly similar
        self.old_pid_list = []  # List of PIDs during last resource check
        self.stable_cpu_ref = None  # CPU usage at last broadcast
        self.stable_io_ref = None  # IO usage at last broadcast
        self.stable_ram_ref = None  # RAM usage at last broadcast
        self.start_time = None  # Time current resource check began
        self.stdin_path = '/dev/null'  # No STDIN
        self.stderr_path = '/dev/null'  # No STDERR
        self.stdout_path = '/dev/null'  # No STDOUT
        self.wall_critical = False  # Broadcast critical resource use
        self.wall_warning = False  # Broadcast high resource use

    @staticmethod
    def is_stable(bound_diff=None, current_state=None,
                  stable_state=None):
        """Determines if resource usage is stable or not

        :param bound_diff: difference from steady state before unstable
        :type bound_diff: float

        :param current_state: current resource usage
        :type current_state: float

        :param stable_state: reference point to determine stability
        :type stable_state: float

        :return: True if resource is table else False
        :rtype: bool
        """

        lower_bound = stable_state - bound_diff
        upper_bound = stable_state + bound_diff
        if current_state < lower_bound or current_state > upper_bound:
            return False  # Unstable
        else:
            return True  # Stable

    @staticmethod
    def non_kernel_pids(pids_list):
        """Filter out kernel processes from a list of process IDs

        :param pids_list: list of pids
        :type pids_list: list

        :return: non-kernel pids
        :rtype: list
        """

        info_logger.info('Filtering out kernel PIDs')
        debug_logger.debug('Raw PID List: {0}'.format(', '.join(pids_list)))
        non_kernel_pids = []
        for pid in pids_list:
            pid_exe_path = '/proc/{0}/exe'.format(str(pid))
            try:
                assert bool(os.readlink(pid_exe_path)) is True  # Link exists
                non_kernel_pids.append(pid)  # Link exists = non-kernel pid
            except (FileNotFoundError, AssertionError):  # Link doesn't exist
                pass  # Link doesn't exist = kernel pid = do not add to list
        info_logger.info('Finished filtering kernel PIDs')
        debug_logger.debug(
                'Filtered PID List: {0}'.format(', '.join(non_kernel_pids)))
        return non_kernel_pids

    @staticmethod
    def wall(resource=None, level=None, usage=None):
        """Attempts to broadcast wall message and logs error if it cannot

        :param resource: resource type ['CPU', 'RAM', 'IO']
        :type resource: str

        :param level: usage level of resource ['Warning', 'Critical']
        :type level: str

        :param usage: resource usage quantity
        :type usage: str, int, or float

        :return: nothing
        :rtype: N/A
        """

        message = '{0} Usage {1}: {2}\nIt is recommended that you do not ' \
                  'start any {0} intensive processes at this ' \
                  'time.'.format(resource, level, str(usage))
        try:
            info_logger.info('Attempting broadcast')
            subprocess.call(['wall', message])
            info_logger.info('Broadcast successful')
        except OSError as error:
            info_logger.info(
                    'Broadcast unsuccessful: see error log for more info')
            error_message = '{0}: Cannot send broadcast via the program ' \
                            '"wall"'.format(error)
            error_logger.error(error_message)

    def check_wall(self):
        """See if daemon can/should broadcast high usage messages via 'wall'

        :returns: nothing
        :rtype: N/A
        """

        if bool(shutil.which('wall')):
            debug_logger.debug('Program "wall" found')
            if self.config['critical_wall_message']:
                self.wall_critical = True
                debug_logger.debug('Critical broadcasts enabled')
            else:
                debug_logger.debug('Critical broadcasts disabled')
            if self.config['warning_wall_message']:
                self.wall_warning = True
                debug_logger.debug('Warning broadcasts enabled')
            else:
                debug_logger.debug('Warning broadcasts disabled')
        else:
            debug_logger.debug('Program "wall" not found')

    def cpu_check(self):
        """Checks CPU usage, logs and/or broadcasts high usage

        :return: nothing
        :rtype: N/A
        """

        info_logger.info('Determining if CPU usage check is needed')

        # Determine if override should be put into effect
        override = False
        if self.last_cpu_override is None:
            override = True
            info_logger.info('CPU usage has never been checked by this '
                             'instance of resource_alerterd: CPU-check '
                             'override activated')
        else:
            delta_override_time = self.start_time - self.last_cpu_override
            debug_logger.debug('CPU override delay time: {0} sec'.format(
                    str(self.config['cpu_override_delay'])))
            debug_logger.debug('Time since last CPU-check override: '
                               '{0} s'.format(str(delta_override_time)))
            if delta_override_time >= self.config['cpu_override_delay']:
                override = True
                info_logger.info('Time since last override is greater than '
                                 'CPU override check delay: CPU-check '
                                 'override activated')

        # Skip CPU usage check if PID lists are similar and override inactive
        if not override and self.pids_same:
            info_logger.info('PIDs are highly similar to last check and '
                             'CPU-check override is not active: skipping CPU '
                             'usage check')
            return  # Exit CPU usage check silently

        # Determine if sufficient time has past since last CPU check to
        # justify checking CPU usage now
        check_cpu = False
        debug_logger.debug('Calculating time since last CPU check')
        if self.last_cpu_check is None:
            check_cpu = True
            info_logger.info('CPU usage has never been checked by this '
                             'instance of resource_alerterd: checking CPU '
                             'usage')
            psutil.cpu_percent()  # Passing first call silently since it is bad
            time.sleep(0.25)  # 0.1 sec minimum required after initial check
        elif override:
            check_cpu = True
            info_logger.info('CPU-check override active: checking CPU usage')
        else:
            delta_check_time = self.start_time - self.last_cpu_check
            debug_logger.debug('CPU check delay time: {0} sec'.format(
                    str(self.config['cpu_check_delay'])))
            debug_logger.debug(
                    'Time since last CPU check: {0} sec'.format(
                            str(delta_check_time)))
            delta_check_ratio = delta_check_time / self.config[
                'cpu_check_delay']
            if delta_check_ratio >= 0.95:
                check_cpu = True
                info_logger.info('Time since last check is close to or '
                                 'greater than CPU check delay time: checking '
                                 'CPU usage')
            else:
                info_logger.info('Time since last check is not close to or '
                                 'greater than delay CPU check delay time: '
                                 'skipping CPU usage check')

        # Check CPU usage and log/broadcast high usage
        if check_cpu:
            info_logger.info('Determining CPU usage')
            cpu_usage = psutil.cpu_percent()
            debug_logger.debug('CPU Usage: {0}%'.format(str(cpu_usage)))

            # See if CPU usage is stable
            debug_logger.debug('Determining if CPU usage has changed '
                               'significantly since last broadcast')
            if self.stable_cpu_ref is None:
                stable = False
                debug_logger.debug('CPU usage has never been checked by this '
                                   'instance of resource_alerted: '
                                   'broadcasting enabled')
            elif override:
                stable = False
                info_logger.info('CPU-check override active: broadcasting '
                                 'enabled')
            else:
                stable = self.is_stable(
                        bound_diff=self.config['cpu_stable_diff'],
                        current_state=cpu_usage,
                        stable_state=self.stable_cpu_ref)
                if not stable:
                    debug_logger.debug('CPU usage has changed significantly '
                                       'since last broadcast: broadcasting '
                                       'enabled')
                else:
                    debug_logger.debug('CPU usage has not changed '
                                       'significantly since last broadcast: '
                                       'broadcasting disabled')

            # Skip logging/broadcast if CPU usage is stable,
            # log/broadcast and reset reference point if not
            if not stable:
                if cpu_usage >= self.config['cpu_critical_level']:
                    self.stable_cpu_ref = cpu_usage  # Reset reference
                    critical_logger.critical(
                            'CPU Usage Critical: {0}%'.format(str(cpu_usage)))
                    if self.wall_critical:  # Broadcast critical CPU usage
                        self.wall(resource='CPU',
                                  level='Critical',
                                  usage=cpu_usage)
                    # If broadcast performed under override, reset override
                    if override:
                        self.last_cpu_override = self.start_time
                        debug_logger.debug('Reset last CPU-check override '
                                           'time')
                elif cpu_usage >= self.config['cpu_warning_level']:
                    self.stable_cpu_ref = cpu_usage  # Reset reference
                    warning_logger.warning('CPU Usage Warning: {0}%'.format(
                            str(cpu_usage)))
                    if self.wall_warning:  # Broadcast CPU usage warning
                        self.wall(resource='CPU',
                                  level='Warning',
                                  usage=cpu_usage)
                    # If broadcast performed under override, reset override
                    if override:
                        self.last_cpu_override = self.start_time
                        debug_logger.debug('Reset last CPU-check override '
                                           'time')
                else:
                    debug_logger.debug('CPU usage is not above Warning or '
                                       'Critical Threshold: skipping '
                                       'broadcast')

            # Reset time since last check
            self.last_cpu_check = self.start_time
            debug_logger.debug('Reset last CPU check time')

    def io_check(self):
        """Checks IO Wait, logs and/or broadcasts high usage

        :return: nothing
        :rtype: N/A
        """

        info_logger.info('Determining if IO usage check is needed')

        # Determine if override should be put into effect
        override = False
        if self.last_io_override is None:
            override = True
            info_logger.info('IO usage has never been checked by this '
                             'instance of resource_alerterd: IO-check '
                             'override activated')
        else:
            delta_override_time = self.start_time - self.last_io_override
            debug_logger.debug('IO override delay time: {0} sec'.format(
                    str(self.config['io_override_delay'])))
            debug_logger.debug('Time since last IO-check override: '
                               '{0} sec'.format(str(delta_override_time)))
            if delta_override_time >= self.config['io_override_delay']:
                override = True
                info_logger.info('Time since last override is greater than '
                                 'IO override check delay: IO-check '
                                 'override activated')

        # Skip IO usage check if PID lists are similar and override inactive
        if not override and self.pids_same:
            info_logger.info('PIDs are highly similar to last check and '
                             'IO-check override is not active: skipping IO '
                             'usage check')
            return  # Exit IO usage check silently

        # Determine if sufficient time has past since last IO check to
        # justify checking IO usage now
        check_io = False
        debug_logger.debug('Calculating time since last IO usage')
        if self.last_io_check is None:
            check_io = True
            info_logger.info('IO usage has never been checked by this '
                             'instance of resource_alerterd: checking IO '
                             'usage')
        elif override:
            check_io = True
            info_logger.info('IO-check override active: checking IO usage')
        else:
            delta_check_time = self.start_time - self.last_io_check
            debug_logger.debug('IO check delay time: {0} sec'.format(
                    str(self.config['io_check_delay'])))
            debug_logger.debug(
                    'Time since last IO check: {0} sec'.format(
                            str(delta_check_time)))
            delta_check_ratio = delta_check_time / self.config[
                'io_check_delay']
            if delta_check_ratio >= 0.95:
                check_io = True
                info_logger.info('Time since last check is close to or '
                                 'greater than IO check delay time: checking '
                                 'IO usage')
            else:
                info_logger.info('Time since last check is not close to or '
                                 'greater than delay IO check delay time: '
                                 'skipping IO usage check')

        # Check IO Wait and log/broadcast high usage
        if check_io:
            info_logger.info('Determining IO usage')
            io_usage = psutil.cpu_times().iowait / self.io_max
            debug_logger.debug('IO Usage: {0}%'.format(str(io_usage)))

            # See if IO usage is stable
            debug_logger.debug('Determining if IO usage has changed '
                               'significantly since last broadcast')
            if self.stable_io_ref is None:
                stable = False
                debug_logger.debug('IO usage has never been checked by this '
                                   'instance of resource_alerted: '
                                   'broadcasting enabled')
            elif override:
                stable = False
                info_logger.info('IO-check override active: broadcasting '
                                 'enabled')
            else:
                stable = self.is_stable(
                        bound_diff=self.config['io_stable_diff'],
                        current_state=io_usage,
                        stable_state=self.stable_io_ref)
                if not stable:
                    debug_logger.debug('IO usage has changed significantly '
                                       'since last broadcast: broadcasting '
                                       'enabled')
                else:
                    debug_logger.debug('IO usage has not changed '
                                       'significantly since last broadcast: '
                                       'broadcasting disabled')

            # Skip logging/broadcast if IO usage is stable,
            # log/broadcast and reset reference point if not
            if not stable:
                if io_usage >= self.config['ram_critical_level']:
                    self.stable_io_ref = io_usage  # Reset reference
                    critical_logger.critical(
                            'IO Usage Critical: {0}%'.format(str(io_usage)))
                    if self.wall_critical:  # Broadcast critical IO usage
                        self.wall(resource='IO',
                                  level='Critical',
                                  usage=io_usage)
                    # If broadcast performed under override, reset override
                    if override:
                        self.last_ram_override = self.start_time
                        debug_logger.debug('Reset last IO-check override '
                                           'time')
                elif io_usage >= self.config['ram_warning_level']:
                    self.stable_ram_ref = io_usage  # Reset reference
                    warning_logger.warning('IO Usage Warning: {0}%'.format(
                            str(io_usage)))
                    if self.wall_warning:  # Broadcast IO usage warning
                        self.wall(resource='IO',
                                  level='Warning',
                                  usage=io_usage)
                    # If broadcast performed under override, reset override
                    if override:
                        self.last_ram_override = self.start_time
                        debug_logger.debug('Reset last IO-check override '
                                           'time')
                else:
                    debug_logger.debug('IO usage is not above Warning or '
                                       'Critical Threshold: skipping '
                                       'broadcast')

            # Reset time since last check
            self.last_io_check = self.start_time
            debug_logger.debug('Reset last IO check time')

    def pids_same_test(self):
        """Determine how similar current PIDs are to last resource check

        :return: nothing
        :rtype: N/A
        """

        new_pid_list = self.non_kernel_pids(psutil.pids())
        info_logger.info('Comparing similarity in PID lists since last '
                         'resource check')
        compare_pids = difflib.SequenceMatcher(new_pid_list,
                                               self.old_pid_list)
        pids_similarity = compare_pids.ratio() * 100.0
        debug_logger.debug('PID lists similarity: {0}%'.format(str(
                pids_similarity)))
        debug_logger.debug('Minimum PID Similarity Permitted: '
                           '{0}%'.format(self.config['min_pid_same']))
        self.old_pid_list = new_pid_list[:]  # Replace old list w/ new list
        if pids_similarity <= self.config['min_pid_same']:
            self.pids_same = False
            info_logger.info('PID lists sufficiently different: '
                             'performing resource checks')
        else:
            self.pids_same = True
            info_logger.info('PID lists sufficiently similar: '
                             'skipping resource checks unless overrides '
                             'activate')

    def ram_check(self):
        """Checks RAM usage, logs and/or broadcasts high usage

        :return: nothing
        :rtype: N/A
        """

        info_logger.info('Determining if RAM usage check is needed')

        # Determine if override should be put into effect
        override = False
        if self.last_ram_override is None:
            override = True
            info_logger.info('RAM usage has never been checked by this '
                             'instance of resource_alerterd: RAM-check '
                             'override activated')
        else:
            delta_override_time = self.start_time - self.last_ram_override
            debug_logger.debug('RAM override delay time: {0} sec'.format(
                    str(self.config['ram_override_delay'])))
            debug_logger.debug('Time since last RAM-check override: '
                               '{0} sec'.format(str(delta_override_time)))
            if delta_override_time >= self.config['ram_override_delay']:
                override = True
                info_logger.info('Time since last override is greater than '
                                 'RAM override check delay: RAM-check '
                                 'override activated')

        # Skip RAM usage check if PID lists are similar and override inactive
        if not override and self.pids_same:
            info_logger.info('PIDs are highly similar to last check and '
                             'RAM-check override is not active: skipping RAM '
                             'usage check')
            return  # Exit RAM usage check silently

        # Determine if sufficient time has past since last RAM check to
        # justify checking RAM usage now
        check_ram = False
        debug_logger.debug('Calculating time since last RAM check')
        if self.last_ram_check is None:
            check_ram = True
            info_logger.info('RAM usage has never been checked by this '
                             'instance of resource_alerterd: checking RAM '
                             'usage')
        elif override:
            check_ram = True
            info_logger.info('RAM-check override active: checking RAM usage')
        else:
            delta_check_time = self.start_time - self.last_ram_check
            debug_logger.debug('RAM check delay time: {0} sec'.format(
                    str(self.config['ram_check_delay'])))
            debug_logger.debug(
                    'Time since last RAM check: {0} sec'.format(
                            str(delta_check_time)))
            delta_check_ratio = delta_check_time / self.config[
                'ram_check_delay']
            if delta_check_ratio >= 0.95:
                check_ram = True
                info_logger.info('Time since last check is close to or '
                                 'greater than RAM check delay time: checking '
                                 'RAM usage')
            else:
                info_logger.info('Time since last check is not close to or '
                                 'greater than delay RAM check delay time: '
                                 'skipping RAM usage check')

        # Check RAM usage and log/broadcast high usage
        if check_ram:
            info_logger.info('Determining RAM usage')
            ram_usage = psutil.virtual_memory().percent
            debug_logger.debug('RAM Usage: {0}%'.format(str(ram_usage)))

            # See if CPU usage is stable
            debug_logger.debug('Determining if RAM usage has changed '
                               'significantly since last broadcast')
            if self.stable_ram_ref is None:
                stable = False
                debug_logger.debug('RAM usage has never been checked by this '
                                   'instance of resource_alerted: '
                                   'broadcasting enabled')
            elif override:
                stable = False
                info_logger.info('RAM-check override active: broadcasting '
                                 'enabled')
            else:
                stable = self.is_stable(
                        bound_diff=self.config['ram_stable_diff'],
                        current_state=ram_usage,
                        stable_state=self.stable_ram_ref)
                if not stable:
                    debug_logger.debug('RAM usage has changed significantly '
                                       'since last broadcast: broadcasting '
                                       'enabled')
                else:
                    debug_logger.debug('RAM usage has not changed '
                                       'significantly since last broadcast: '
                                       'broadcasting disabled')

            # Skip logging/broadcast if RAM usage is stable,
            # log/broadcast and reset reference point if not
            if not stable:
                if ram_usage >= self.config['ram_critical_level']:
                    self.stable_ram_ref = ram_usage  # Reset reference
                    critical_logger.critical(
                            'RAM Usage Critical: {0}%'.format(str(ram_usage)))
                    if self.wall_critical:  # Broadcast critical RAM usage
                        self.wall(resource='RAM',
                                  level='Critical',
                                  usage=ram_usage)
                    # If broadcast performed under override, reset override
                    if override:
                        self.last_ram_override = self.start_time
                        debug_logger.debug('Reset last RAM-check override '
                                           'time')
                elif ram_usage >= self.config['ram_warning_level']:
                    self.stable_ram_ref = ram_usage  # Reset reference
                    warning_logger.warning('RAM Usage Warning: {0}%'.format(
                            str(ram_usage)))
                    if self.wall_warning:  # Broadcast RAM usage warning
                        self.wall(resource='RAM',
                                  level='Warning',
                                  usage=ram_usage)
                    # If broadcast performed under override, reset override
                    if override:
                        self.last_ram_override = self.start_time
                        debug_logger.debug('Reset last RAM-check override '
                                           'time')
                else:
                    debug_logger.debug('RAM usage is not above Warning or '
                                       'Critical Threshold: skipping '
                                       'broadcast')

            # Reset time since last check
            self.last_ram_check = self.start_time
            debug_logger.debug('Reset last RAM check time')

    def run(self):
        """Main loop for daemon

        :return: nothing
        :rtype: N/A
        """

        # See if OS has 'wall' command to broadcast resource usage
        self.check_wall()

        # Calculate maximum acceptable IO Wait
        self.io_max = 100.0 / float(psutil.cpu_count())

        # Main daemon
        while True:
            # Pre-resource check necessities
            self.start_time = time.time()
            info_logger.info('Starting resource check')
            self.pids_same_test()

            # Run resource checks
            self.cpu_check()
            self.ram_check()
            self.io_check()
            info_logger.info('Resource check complete')

            # Determine sleep time until next resource check
            time.sleep(self.sleep_time())

    def sleep_time(self):
        """Calculate time until next resource check is required

        :return: time for daemon to sleep
        :rtype: float
        """

        debug_logger.debug('Calculating time until next resource check')
        next_cpu_check = self.last_cpu_check + config_dict['cpu_check_delay']
        next_io_check = self.last_io_check + config_dict['io_check_delay']
        next_ram_check = self.last_ram_check + config_dict['ram_check_delay']
        next_resource_check = min(next_cpu_check,
                                  next_io_check,
                                  next_ram_check)
        sleep_time = next_resource_check - time.time()
        sleep_time = 0 if sleep_time < 0 else sleep_time  # Avoid negatives
        info_logger.info('Sleeping for {0} sec'.format(sleep_time))
        return sleep_time


if __name__ == '__main__':
    # Parse configuration file and instantiate class
    config_file = resource_stream('resource_alerter', 'resource_alerterd.conf')
    config_dict = yaml.load(config_file)
    resource_alerter = ResourceAlerter(config_dict)

    # Parse logging config file and create loggers
    log_config_file = resource_stream('resource_alerter',
                                      'resource_alerterd.logging.conf')
    logging_config_dict = yaml.load(log_config_file)
    logging.config.dictConfig(logging_config_dict)
    debug_logger = logging.getLogger('debug_logger')
    info_logger = logging.getLogger('info_logger')
    warning_logger = logging.getLogger('warning_logger')
    error_logger = logging.getLogger('error_logger')
    critical_logger = logging.getLogger('critical_logger')
    loggers = [debug_logger, info_logger, warning_logger, error_logger,
               critical_logger]

    # Ensure that logging files are available after daemon-ization
    files_to_preserve = []
    for logger in loggers:
        for i in range(len(logger.handlers)):
            file_stream = logger.handlers[i].stream
            if file_stream not in files_to_preserve:
                files_to_preserve.append(file_stream)

    # Create daemon
    daemon_runner = runner.DaemonRunner(resource_alerter)
    daemon_runner.daemon_context.files_preserve = files_to_preserve
    daemon_runner.do_action()

    sys.exit(0)
