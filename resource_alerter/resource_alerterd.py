#! /usr/bin/env python

"""Monitors CPU and RAM usage, logs/broadcasts high usage

Usage:

    resource_alerterd.py [--systemd] { start | stop | restart }

Synopsis:

    resource_alerterd is a Python daemon designed for Unix-like systems. As
    the name, it monitors system resource usage and alerts users to high
    resource usage. Specifically, resource_alerterd monitors CPU and RAM
    usage and logs use above specified percentage thresholds. Many aspects
    of the alerting algorithm are customizable in the configuration file.
    This program should be run with root permissions to function properly.
    See README.md for more details.

Arguments:

    --systemd:  Runs resource_alerterd in systemd-compatibility mode,
                forking type in systemd unit scripts should be set to 'simple'

    { start | stop | restart }: For all tested cases other than systemd,
                                resource_alerterd will double fork in order to
                                daemonize. These three options control the
                                daemon.

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

import difflib
import logging
import logging.config
import os
from pkg_resources import resource_stream
import psutil
from ra_daemon import runner
import subprocess
import sys
import time
import yaml

__author__ = 'Alex Hyer'
__email__ = 'theonehyer@gmail.com'
__license__ = 'GPLv3'
__maintainer__ = 'Alex Hyer'
__status__ = 'Production'
__version__ = '1.0.0'


class ResourceAlerter:
    """Daemon-ized, checks various resource usage and alerts users

    This class is, for most intents and purposes, the actual run time process
    of resource_alerterd. In brief, this class monitors CPU and RAM
    usage and then alerts users to high usage of these resources. High
    resource usage is both logged as per resource_alerterd.logging.conf
    and is broadcasted via the program 'wall' if wall is available and
    resource_alerterd is configured to use wall as per resource_alerterd.conf.

    Attributes:
        config (dict): Program configuration options

        last_cpu_check (float): Seconds since CPU usage last checked

        last_cpu_override (float): Seconds since last CPU override check

        last_ram_check (float): Seconds since RAM usage last checked

        last_ram_override (float): Seconds since last RAM override check

        pidfile_path (str): File path to PID file

        pidfile_timeout (int): Max time between successful acces to PID file
            before exiting

        pids_same (bool): True if PIDs of current resource usage check are
        highly similar to the last resource check as defined in in config

        old_pid_list (list): List of non-kernal PIDs from last resource usage
            check

        stable_cpu_ref (float): CPU usage of last high CPU usage broadcast

        stable_ram_ref (float): RAM usage of last high RAM usage broadcast

        start_time (float): Start of current resource check in seconds since
            Epoch (beginning of time)

        stdin_path (str): File path for STDIN

        stdierr_path (str): File path for STDERR

        stdout_path (str): File path for STDOUT
    """

    def __init__(self, config):
        """Initializes many essential daemon-wide run-time variables"""

        self.config = config  # Dictionary from YAML configuration file
        self.last_cpu_check = None
        self.last_cpu_override = None
        self.last_ram_check = None
        self.last_ram_override = None
        self.pidfile_path = '/var/run/resource_alerterd/resource_alerterd.pid'
        self.pidfile_timeout = 5
        self.pids_same = False
        self.old_pid_list = []
        self.stable_cpu_ref = None
        self.stable_ram_ref = None
        self.start_time = None
        self.stdin_path = '/dev/null'  # No STDIN
        self.stderr_path = '/dev/null'  # No STDERR
        self.stdout_path = '/dev/null'  # No STDOUT
        self.wall_critical = False  # Broadcast critical resource use
        self.wall_warning = False  # Broadcast high resource use

    @staticmethod
    def is_stable(bound_diff=None, current_state=None,
                  stable_state=None):
        """Determines if resource usage is stable or not

        Args:
            bound_diff (float): Max difference between stable_state and
                current_state considered stable

            current_state (float): Current resource usage

            stable_state (float): Resource usage of last high resource usage
                broadcastpoint to determine stability

        Returns:
            bool: True if abs(stable_state - current_state) > bound_diff,
                else False, i.e. True if resource usage is stable else False
        """

        lower_bound = stable_state - bound_diff
        upper_bound = stable_state + bound_diff
        if current_state < lower_bound or current_state > upper_bound:
            return False
        else:
            return True

    @staticmethod
    def non_kernel_pids(pids_list):
        """Filter out kernel processes from a list of process IDs

        Args:
            pids_list (list): List of PIDs

        Returns:
            list: List of non-kernal PIDs
        """

        info_logger.info('Filtering out kernel PIDs')
        non_kernel_pids = []
        for pid in pids_list:
            pid_exe_path = '/proc/{0}/exe'.format(str(pid))
            try:
                assert bool(os.readlink(pid_exe_path)) is True  # Link exists
                non_kernel_pids.append(pid)  # Link exists = non-kernel pid
            except (OSError, AssertionError):  # Link doesn't exist
                pass  # Link doesn't exist = kernel pid = do not add to list
        info_logger.info('Finished filtering kernel PIDs')
        return non_kernel_pids

    @staticmethod
    def wall(resource=None, level=None, usage=None):
        """Attempts to broadcast wall message and logs error if it cannot

        Args:
            resource (str): Resource to broadcast hig usage of

            level (str): Level of urgency for high resource usage, i.e.
                'Warning,' 'Critical,' etc.

            usage (float): Current resource usage, converted to str
        """

        message = '{0} Usage {1}: {2}%\nIt is recommended that you do not ' \
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

    # This method is literally just the Python 3.5.1 which function from the
    # shutil library in order to permit this functionality in Python 2.
    # Minor changes to style wer made to account for indentation.
    @staticmethod
    def which(cmd, mode=os.F_OK | os.X_OK, path=None):
        """Given a command, mode, and a PATH string, return the path which
        conforms to the given mode on the PATH, or None if there is no such
        file.

        `mode` defaults to os.F_OK | os.X_OK. `path` defaults to the result
        of os.environ.get("PATH"), or can be overridden with a custom search
        path.
        """

        # Check that a given file can be accessed with the correct mode.
        # Additionally check that `file` is not a directory, as on Windows
        # directories pass the os.access check.
        def _access_check(fn, mode):
            return (os.path.exists(fn) and os.access(fn, mode)
                    and not os.path.isdir(fn))

        # If we're given a path with a directory part, look it up directly
        # rather than referring to PATH directories. This includes checking
        # relative to the current directory, e.g. ./script
        if os.path.dirname(cmd):
            if _access_check(cmd, mode):
                return cmd
            return None

        if path is None:
            path = os.environ.get("PATH", os.defpath)
        if not path:
            return None
        path = path.split(os.pathsep)

        if sys.platform == "win32":
            # The current directory takes precedence on Windows.
            if not os.curdir in path:
                path.insert(0, os.curdir)
            # PATHEXT is necessary to check on Windows.
            pathext = os.environ.get("PATHEXT", "").split(os.pathsep)
            # See if the given file matches any of the expected path
            # extensions. This will allow us to short circuit when given
            # "python.exe". If it does match, only test that one, otherwise
            # we have to try others.
            if any(cmd.lower().endswith(ext.lower()) for ext in
                   pathext):
                files = [cmd]
            else:
                files = [cmd + ext for ext in pathext]
        else:
            # On other platforms you don't have things like PATHEXT to tell you
            # what file suffixes are executable, so just pass on cmd as-is.
            files = [cmd]

        seen = set()
        for dir in path:
            normdir = os.path.normcase(dir)
            if not normdir in seen:
                seen.add(normdir)
                for thefile in files:
                    name = os.path.join(dir, thefile)
                    if _access_check(name, mode):
                        return name
        return None

    def check_wall(self):
        """See if daemon can/should broadcast high usage messages via 'wall'

        Does not return anything; directly changes run-time variable of
        wall_critical and wall_warning.
        """

        if bool(self.which('wall')):
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
        """Checks CPU usage, logs and/or broadcasts high usage"""

        info_logger.info('Determining if CPU usage check is needed')

        # Determine if override should be put into effect
        override = False
        if self.last_cpu_override is None:
            override = True
            self.last_cpu_override = self.start_time
            info_logger.info('CPU usage has never been checked by this '
                             'instance of resource_alerterd: CPU-check '
                             'override activated')
        else:
            delta_override_time = self.start_time - self.last_cpu_override
            debug_logger.debug('CPU override delay time: {0} sec'.format(
                    str(self.config['cpu_override_delay'])))
            debug_logger.debug('Time since last CPU-check override: '
                               '{0} sec'.format(str(delta_override_time)))
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
            self.last_cpu_check = self.start_time
            debug_logger.debug('Reset last CPU check time')
            return  # Exit CPU usage check silently

        # Determine if sufficient time has past since last CPU check to
        # justify checking CPU usage now
        check_cpu = False
        info_logger.info('Calculating time since last CPU check')
        if self.last_cpu_check is None:
            check_cpu = True
            self.last_cpu_check = self.start_time
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
            info_logger.info('CPU Usage: {0}%'.format(str(cpu_usage)))

            # See if CPU usage is stable
            info_logger.info('Determining if CPU usage has changed '
                             'significantly since last broadcast')
            if self.stable_cpu_ref is None:
                stable = False
                info_logger.info('No CPU stability reference: '
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
                    info_logger.info('CPU usage has changed significantly '
                                     'since last broadcast: broadcasting '
                                     'enabled')
                else:
                    info_logger.info('CPU usage has not changed '
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
                    info_logger.info('CPU usage is not above Warning or '
                                     'Critical Threshold: skipping '
                                     'broadcast')

        # Reset time since last check
        self.last_cpu_check = self.start_time
        debug_logger.debug('Reset last CPU check time')

    def pids_same_test(self):
        """Determine how similar current PIDs are to last resource check"""

        new_pid_list = self.non_kernel_pids(psutil.pids())
        info_logger.info('Comparing similarity in PID lists since last '
                         'resource check')
        compare_pids = difflib.SequenceMatcher(None,
                                               self.old_pid_list,
                                               new_pid_list)
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
        """Checks RAM usage, logs and/or broadcasts high usage"""

        info_logger.info('Determining if RAM usage check is needed')

        # Determine if override should be put into effect
        override = False
        if self.last_ram_override is None:
            override = True
            self.last_ram_override = self.start_time
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
            self.last_ram_check = self.start_time
            debug_logger.debug('Reset last RAM check time')
            return  # Exit RAM usage check silently

        # Determine if sufficient time has past since last RAM check to
        # justify checking RAM usage now
        check_ram = False
        info_logger.info('Calculating time since last RAM check')
        if self.last_ram_check is None:
            check_ram = True
            self.last_ram_check = self.start_time
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
            info_logger.info('RAM Usage: {0}%'.format(str(ram_usage)))

            # See if CPU usage is stable
            info_logger.info('Determining if RAM usage has changed '
                             'significantly since last broadcast')
            if self.stable_ram_ref is None:
                stable = False
                info_logger.info('No RAM stability reference: '
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
                    info_logger.info('RAM usage has changed significantly '
                                     'since last broadcast: broadcasting '
                                     'enabled')
                else:
                    info_logger.info('RAM usage has not changed '
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
                    info_logger.info('RAM usage is not above Warning or '
                                     'Critical Threshold: skipping '
                                     'broadcast')

        # Reset time since last check
        self.last_ram_check = self.start_time
        debug_logger.debug('Reset last RAM check time')

    def run(self):
        """Main loop for daemon"""

        # See if OS has 'wall' command to broadcast resource usage
        self.check_wall()

        # Main daemon
        while True:
            # Pre-resource check necessities
            self.start_time = time.time()
            info_logger.info('Starting resource check')
            self.pids_same_test()

            # Run resource checks
            self.cpu_check()
            self.ram_check()
            info_logger.info('Resource check complete')

            # Determine sleep time until next resource check
            time.sleep(self.sleep_time())

    def sleep_time(self):
        """Calculate time until next resource check is required"""

        debug_logger.debug('Calculating time until next resource check')
        next_cpu_check = self.last_cpu_check + config_dict['cpu_check_delay']
        next_ram_check = self.last_ram_check + config_dict['ram_check_delay']
        next_resource_check = min(next_cpu_check,
                                  next_ram_check)
        sleep_time = float(next_resource_check - time.time())
        sleep_time = 0 if sleep_time < 0 else sleep_time  # Avoid negatives
        info_logger.info('Sleeping for {0} sec'.format(str(sleep_time)))
        return sleep_time


if __name__ == '__main__':

    # Test for runtime folder and create if needed
    runtime_folder = '/var/run/resource_alerterd'
    if not os.path.isdir(runtime_folder):
        os.mkdir(runtime_folder)

    # Test for logging folder and create if needed
    logging_folder = '/var/log/resource_alerter'
    if not os.path.isdir(logging_folder):
        os.mkdir(logging_folder)

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

    # Run resource_alerterd in systemd-compatible mode else daemonize
    if sys.argv[1] == '--systemd':
        resource_alerter.run()
    else:
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
