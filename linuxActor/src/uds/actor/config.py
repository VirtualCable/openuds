'''
Created on Nov 17, 2011

@author: dkmaster
'''
import os

# Config file format:
# [broker]
# server = host:port (required)
# ssl = [True|False] (defaults to False)
# timeout = Timeout in seconds for xmlrpc (defaults to 10)
# [logging]
# log = /path/to/log (required, defaults to /tmp/udsactor.log)
# debug = [ERROR|INFO|DEBUG|WARN| (defaults to ERROR)
# maxsize = Max size of log file, in megas (defaults to 20)
# backups = Number of backups to keep of log file (defaults to 3)


import ConfigParser
import logging
import sys

CONFIGFILE = '/etc/udsactor/udsactor.cfg'

cfg = ConfigParser.SafeConfigParser(defaults={ 'server' : '', 'ssl' : False, 'timeout' : '10',
                                               'log' : '/tmp/udsactor.log', 'debug' : 'ERROR', 'maxsize'  : '20', 'backups' : '3' })
cfg.read(CONFIGFILE)

levels = {
          'WARN' : logging.WARN,
          'INFO' : logging.INFO,
          'DEBUG': logging.DEBUG,
          'ERROR': logging.ERROR
    }
try:
    config = {
        'server' : cfg.get('broker', 'server'),
        'ssl' : cfg.getboolean('broker', 'ssl'),
        'timeout' : cfg.getint('broker', 'timeout'),
        'log' : cfg.get('logging', 'log'),
        'debug' : levels.get(cfg.get('logging', 'debug'), logging.ERROR),
        'maxsize' : cfg.getint('logging', 'maxsize') * 1024 * 1024,
        'backups' : cfg.getint('logging', 'backups')
        }
    # Config file is used only in "root mode", in user mode we overwrite it
    if os.getuid() != 0:
        config['log'] = os.getenv('HOME', '/tmp') + "/udsactor.log"
except Exception, e:
    sys.stderr.write("Error reading configuration file: " + str(e))
    sys.exit(2)

