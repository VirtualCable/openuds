# -*- coding: utf-8 -*-
'''
Created on Nov 17, 2011

@author: dkmaster
'''
import platform, logging, os, sys, pkgutil

logger = logging.getLogger(__name__)

renamers = {}

def rename(newName):
    distribution = platform.dist()[0].lower()
    if renamers.has_key(distribution):
        return renamers[distribution](newName)
    
    logger.error('Renamer for platform "{0}" not found'.format(distribution))
    return False

pkgpath = os.path.dirname(sys.modules[__name__].__file__)
for _, name, _ in pkgutil.iter_modules([pkgpath]):
    __import__(name, globals(), locals(), [], -1)
