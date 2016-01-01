#! /usr/bin/env python

"""Monitors CPU, RAM, and IO wait

NEEDS ROOT PERMISSIONS TO RUN!
"""

from daemon import runner
import difflib
import logging
import logging.config
import os
from pkg_resources import resource_string
import psutil
import shutil
import subprocess
import sys
import time
import yaml

__version__ = '0.0.0a1'


class ResourceAlerter:
    def __init__(self, config):
        self.config = config
        self.last_cpu_check = None
        self.last_io_check = None
        self.last_ram_check = None
        self.pidfile_path = '/var/run/resource_alerterd/resource_alerterd.pid'
        self.pidfile_timeout = 5
        self.old_pid_list = []
        self.start_time = None
        self.stdin_path = '/dev/null'
        self.stderr_path = '/dev/null'
        self.stdout_path = '/dev/null'
        self.wall_critical = False
        self.wall_warning = False

    def cpu_check(self):
        """Checks CPU usage

        :return: does not return anything
        :rtype: N/A
        """

        info_logger.info('Starting CPU usage check')
        debug_logger.debug('Calculating time since last CPU check')
        if self.last_cpu_check is None:
            delta_check_ratio = None
            info_logger.info('CPU usage has never been checked by this '
                             'instance of resource_alerterd')
            psutil.cpu_percent()  # Passing first call silently since it is bad
            time.sleep(0.5)  # 0.1 sec minimum required after initial check
        else:
            delta_check_time = self.start_time - self.last_cpu_check
            debug_logger.debug(
                    'Time since last CPU check: {0}'.format(delta_check_time))
            delta_check_ratio = delta_check_time / self.config[
                'cpu_check_delay']
        debug_logger.debug('CPU check delay time: {0}'.format(
                self.config['cpu_check_delay']))
        if delta_check_ratio >= 0.95 or delta_check_ratio is None:
            info_logger.info('Time since last check is close to or greater '
                             'than delay time: checking cpu usage')
            cpu_usage = psutil.cpu_percent()
            debug_logger.debug('CPU Usage: {0}'.format(cpu_usage))
            if cpu_usage >= self.config['cpu_critical_level']:
                critical_logger.critical(
                        'CPU Usage Critical: {0}'.format(cpu_usage))
                if self.wall_critical:
                    message = 'CPU Usage Critical: {0}\nIt is recommended ' \
                              'that you do not start any CPU intensive ' \
                              'processes at this time.'
                    subprocess.call(['wall', message])
            elif cpu_usage >= self.config['cpu_warning_level']:
                warning_logger.warning('CPU Usage Warning: {0}'.format(
                        cpu_usage))
                if self.wall_warning:
                    message = 'CPU Usage Warning: {0}\nIt is recommended ' \
                              'that you do not start any CPU intensive ' \
                              'processes at this time.'
                    subprocess.call(['wall', message])
            self.last_cpu_check = time.time()
            info_logger.info('CPU usage check complete')
        else:
            info_logger.info('Time since last check is not close to or '
                             'greater than delay time: skipping cpu usage '
                             'check')

    def non_kernel_pids(self, pids_list):
        """Filter out kernel processes from a list of process IDs

        :param pids_list: list of pids
        :type pids_list: list

        :return: non-kernel pids
        :rtype: list
        """

        info_logger.info('Filtering out kernel PIDs')
        debug_logger.debug('Raw PID List:\n{0}'.format('\n'.join(pids_list)))
        non_kernel_pids = []
        for pid in pids_list:
            pid_exe_path = '/proc/{0}/exe'.format(str(pid))
            try:
                assert bool(os.readlink(pid_exe_path)) is True  # Link exists
                non_kernel_pids.append(pid)  # Link exists = non-kernel pid
            except FileNotFoundError:  # Link doesn't exist
                pass  # Link doesn't exist = kernel-pid
        info_logger.info('Finished filtering kernel PIDs')
        debug_logger.debug(
                'Filtered PID List\n{0}'.format('\n'.join(non_kernel_pids)))
        return non_kernel_pids

    def run(self):
        # See if OS has 'wall_critical' command to broadcast resource usage
        if bool(shutil.which('wall')):
            if self.config['critical_wall_message']:
                self.wall_critical = True
            if self.config['warning_wall_message']:
                self.wall_warning = True
        # Main daemon
        while True:
            self.start_time = time.time()
            info_logger.info('Starting resource check')
            new_pid_list = self.non_kernel_pids(psutil.pids())
            info_logger.info('Comparing similarity in PID lists since last '
                             'resource check')
            compare_pids = difflib.SequenceMatcher(new_pid_list,
                                                   self.old_pid_list)
            debug_logger.debug('PID lists similarity: {0}'.format(str(
                    compare_pids.ratio())))
            debug_logger.debug('Minimum PID Similarity Permitted: '
                               '{0}'.format(self.config['min_pid_same']))
            if compare_pids.ratio() <= self.config['min_pid_same']:
                info_logger.info('PID lists sufficiently different: '
                                 'performing resource check')
                self.cpu_check()
            else:
                info_logger.info('PID lists sufficiently similar: '
                                 'skipping resource check')
                # TODO: Time calculations here


if __name__ == '__main__':
    # Parse configuration file and instantiate class
    with open(resource_string(__file__, 'resource_alerted.conf'), 'rU') as \
            config_handle:
        config_dict = yaml.load(config_handle)
    resource_alerter = ResourceAlerter(config_dict)

    # Parse logging config file and create loggers
    with open(resource_string(__file__, 'resource_alerterd.logging.conf'),
              # with open('/usr/lib/python3.4/site-packages'
              #           '/resource_alerter/resource_alerterd.logging.conf',
              'rU') as config_handle:
        logging_config_dict = yaml.load(config_handle)
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
