# -*- coding: utf-8 -*-
'''
Created on Nov 16, 2011

@author: dkmaster
'''
import logging, logging.handlers
from config import config

# Initializes logging facility (don't using dictConfig)

log = logging.getLogger('uds')
log.setLevel(config['debug'])

formatter = logging.Formatter('%(levelname)s %(asctime)s %(module)s %(message)s')

fileHandler = logging.handlers.RotatingFileHandler(filename = config['log'], mode = 'a', maxBytes = config['maxsize'], backupCount = config['backups'], encoding = 'utf-8')
fileHandler.setLevel(logging.DEBUG)
fileHandler.setFormatter(formatter)

#streamHandler = logging.StreamHandler()
#streamHandler.setLevel(logging.DEBUG)
#streamHandler.setFormatter(formatter)

log.addHandler(fileHandler)
#log.addHandler(streamHandler)
