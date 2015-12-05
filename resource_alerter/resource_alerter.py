#! /usr/bin/env python

"""


"""

import argparse
from daemon import runner
import logging
import logging.config
from pkg_resources import resource_string
import sys
import yaml

__version__ = '0.0.0a1'


class ResourceAlerter():
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
    # TODO: Put argparse code here

    resource_alerter = ResourceAlerter()
    with open(resource_string(__file__, 'resource_alerter.logging.conf'),
              'rU') as config_handle:
        config_dict = yaml.load(config_handle)
    logging.config.dictConfig(config_dict)
    daemon_runner = runner.DaemonRunner(resource_alerter)
    daemon_runner.daemon_context.files_preserve = \
        [config_dict['handlers'][handler]['filename'] for handler in
         config_dict['handlers'].keys()]
    daemon_runner.do_action()

    sys.exit(0)
