#! /usr/bin/env python

"""


"""

from daemon import runner
import logging
import logging.config
from pkg_resources import resource_string
import sys
import time
import yaml

__version__ = '0.0.0a1'


class ResourceAlerter:
    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = '/dev/null'
        self.stderr_path = '/dev/null'
        self.pidfile_path = '/var/run/resource_alerter/resource_alerter.pid'
        self.pidfile_timeout = 5

    def run(self):
        while True:
            pass
            # TODO: Put code here


if __name__ == '__main__':
    resource_alerter = ResourceAlerter()
    # with open(resource_string(__file__, 'resource_alerter.logging.conf'),
    with open('/usr/lib/python3.4/site-packages'
              '/resource_alerter/resource_alerter.logging.conf',
              'rU') as config_handle:
        config_dict = yaml.load(config_handle)
    logging.config.dictConfig(config_dict)
    debug_logger = logging.getLogger('debug_logger')
    info_logger = logging.getLogger('info_logger')
    warning_logger = logging.getLogger('warning_logger')
    error_logger = logging.getLogger('error_logger')
    critical_logger = logging.getLogger('critical_logger')
    loggers = [debug_logger, info_logger, warning_logger, error_logger,
               critical_logger]
    files_to_preserve = []
    for logger in loggers:
        for i in range(len(logger.handlers)):
            file_stream = logger.handlers[i].stream
            if file_stream not in files_to_preserve:
                files_to_preserve.append(file_stream)
    daemon_runner = runner.DaemonRunner(resource_alerter)
    daemon_runner.daemon_context.files_preserve = files_to_preserve
    daemon_runner.do_action()

    sys.exit(0)
