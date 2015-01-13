#
# Copyright (c) 2014, Arista Networks, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#   Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
#
#   Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
#
#   Neither the name of Arista Networks nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL ARISTA NETWORKS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN
# IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
# pylint: disable=C0103
#

import argparse
import logging
import os
import sys

from wsgiref.simple_server import make_server


from ztpserver import config, controller

from ztpserver.serializers import load
from ztpserver.validators import NeighbordbValidator
from ztpserver.constants import CONTENT_TYPE_YAML
from ztpserver.topology import neighbordb_path
from ztpserver.utils import all_files

DEFAULT_CONF = config.GLOBAL_CONF_FILE_PATH

log = logging.getLogger("ztpserver")
log.setLevel(logging.DEBUG)
log.addHandler(logging.NullHandler())

def enable_handler_console(level=None):
    """ Enables logging to stdout """
    
    logging_fmt = config.runtime.default.console_logging_format
    formatter = logging.Formatter(logging_fmt)

    ch = logging.StreamHandler()
    ch.tag = 'console'

    
    for handler in log.handlers:
        if 'tag' in handler.__dict__ and handler.tag == ch.tag:
            # Handler previously added
            return

    level = level or 'DEBUG'
    level = str(level).upper()
    level = logging.getLevelName(level)
    ch.setLevel(level)
    ch.setFormatter(formatter)

    log.addHandler(ch)

def python_supported():
    """ Returns True if the current version of the python runtime is valid """
    return sys.version_info > (2, 7) and sys.version_info < (3, 0)

def start_logging(debug):
    """ reads the runtime config and starts logging if enabled """

    if config.runtime.default.logging:
        if config.runtime.default.console_logging:
            enable_handler_console('DEBUG' if debug else 'INFO')

def load_config(conf=None):
    conf = conf or DEFAULT_CONF
    conf = os.environ.get('ZTPS_CONFIG', conf)

    if os.path.exists(conf):
        config.runtime.read(conf)

def start_wsgiapp():
    """ Provides the entry point into the application for wsgi compliant
    servers.   Accepts a single keyword argument ``conf``.   The ``conf``
    keyword argument specifies the path the server configuration file.  The
    default value is /etc/ztpserver/ztpserver.conf.

    :param conf: string path pointing to configuration file
    :return: a wsgi application object

    """

    log.info('Logging started for ztpserver')
    log.info('Using repository %s', config.runtime.default.data_root)

    if not python_supported():
        raise SystemExit('ERROR: ZTPServer requires Python 2.7')

    return controller.Router()

def run_server(version):
    """ The :py:func:`run_server` is called by the main command line routine to
    run the server as standalone.   This function accepts a single argument
    that points towards the configuration file describing this server

    This function will block on the active thread until stopped.

    :param conf: string path pointing to configuration file
    """

    app = start_wsgiapp()

    host = config.runtime.server.interface
    port = config.runtime.server.port

    httpd = make_server(host, port, app)

    log.info("Starting ZTPServer v%s on http://%s:%s" % 
             (version, host, port))

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info('Shutdown...')

def run_validator():

    # Validating neighbordb
    validator = NeighbordbValidator('N/A')
    neighbordb = neighbordb_path()
    print 'Validating neighbordb (\'%s\')...' % neighbordb
    try:
        validator.validate(load(neighbordb, CONTENT_TYPE_YAML,
                                'validator'))
        total_patterns = len(validator.valid_patterns) + \
            len(validator.invalid_patterns)
            
        if validator.invalid_patterns:
            print '\nERROR: Failed to validate neighbordb patterns'
            print '   Invalid Patterns (count: %d/%d)' % \
                (len(validator.invalid_patterns),
                 total_patterns)
            print '   ---------------------------'
            for index, pattern in enumerate(
                sorted(validator.invalid_patterns)):
                print '   [%d] %s' % (index, pattern[1])
        else:
            print 'Ok!'            
    except Exception as exc:        #pylint: disable=W0703
        print 'ERROR: Failed to validate neighbordb\n%s' % exc

    data_root = config.runtime.default.data_root

    print '\nValidating definitions...'
    for definition in all_files(os.path.join(data_root, 
                                             'definitions')):
        print 'Validating %s...' % definition,
        try:
            load(definition, CONTENT_TYPE_YAML,
                 'validator')
            print 'Ok!'
        except Exception as exc:        #pylint: disable=W0703            
            print '\nERROR: Failed to validate %s\n%s' % \
                (definition, exc)

    print '\nValidating resources...'
    for resource in all_files(os.path.join(data_root, 
                                             'resources')):
        print 'Validating %s...' % resource,
        try:
            load(resource, CONTENT_TYPE_YAML,
                 'validator')
            print 'Ok!'
        except Exception as exc:        #pylint: disable=W0703            
            print '\nERROR: Failed to validate %s\n%s' % \
                (resource, exc)

    print '\nValidating nodes...'
    for filename in [x for x in all_files(os.path.join(data_root, 
                                                       'nodes'))
                     if x.split('/')[-1] in ['definition',
                                             'pattern']]:
        print 'Validating %s...' % filename,
        try:
            load(filename, CONTENT_TYPE_YAML,
                 'validator')
            print 'Ok!'
        except Exception as exc:        #pylint: disable=W0703            
            print '\nERROR: Failed to validate %s\n%s' % \
                (filename, exc)

def main():
    """ The :py:func:`main` is the main entry point for the ztpserver if called
    from the commmand line.   When called from the command line, the server is
    running in standalone mode as opposed to using the :py:func:`application` to
    run under a python wsgi compliant server
    """

    usage = 'ztpserver [options]'

    parser = argparse.ArgumentParser(usage=usage)

    parser.add_argument('--version', '-v',
                        action='store_true',
                        help='Displays the version information')

    parser.add_argument('--conf', '-c',
                        type=str,
                        default=DEFAULT_CONF,
                        help='Specifies the configuration file to use')

    parser.add_argument('--validate-config', '-V',
                        action='store_true',
                        help='Validates config files')

    parser.add_argument('--debug',
                        action='store_true',
                        help='Enables debug output to the STDOUT')


    args = parser.parse_args()

    version = 'N/A'
    try:
        version = open(config.VERSION_FILE_PATH).read().split()[0].strip()
    except IOError:
        pass

    if args.version:
        print 'ZTPServer version %s' % version
        sys.exit()

    load_config(args.conf)
    start_logging(args.debug)

    if args.validate_config:
        sys.exit(run_validator())

    return run_server(version)
