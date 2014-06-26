# -*- coding: utf-8 -*-
'''
Created on Nov 17, 2011

@author: dkmaster
'''
import logging, xmlrpclib, socket
import net
from config import config

logger = logging.getLogger(__name__)

LOGIN_MSG = 'login'
LOGOUT_MSG = 'logout'
READY_MSG = 'ready'
INFO_MSG = 'information'
IP_MSG = 'ip'

class Rpc(object):

    _manager = None

    def __init__(self, broker, ssl, timeout=10):
        url = (ssl and 'https' or 'http') + '://' + broker + '/xmlrpc'
        logger.debug('Remote address: {0}'.format(url))
        self._server = xmlrpclib.ServerProxy(uri=url, verbose=False)
        self._id = None
        socket.setdefaulttimeout(timeout)

    @staticmethod
    def initialize():
        Rpc._manager = Rpc(config['server'], config['ssl'], config['timeout'])

    def test(self):
        try:
            self._server.test()
            logger.debug('Test successful')
            return True
        except Exception:
            logger.error('Test unsuccessful')
            return False

    def message(self, msg, data):
        try:
            if self._id is None:
                self._id = ','.join([ v['mac'] for v in net.getExternalIpAndMacs().values() ])
            logger.debug('Sending message to broker: {0} -> {1}, {2}'.format(self._id, msg, data))
            return self._server.message(self._id, msg, data)
        except Exception as e:
            logger.exception('Error notifying message')
            return None
        return ''

    @staticmethod
    def login(username):
        if Rpc._manager is None:  # Not managed
            return
        return Rpc._manager.message(LOGIN_MSG, username)

    @staticmethod
    def logout(username):
        if Rpc._manager is None:  # Not managed
            return
        return Rpc._manager.message(LOGOUT_MSG, username)

    @staticmethod
    def getInfo():
        if Rpc._manager is None:  # Not managed
            return
        return Rpc._manager.message(INFO_MSG, '')

    @staticmethod
    def setReady():
        if Rpc._manager is None:  # Not managed
            return
        interfaces = ','.join([ v['mac'] + '=' + v['ip'] for v in net.getExternalIpAndMacs().values() ])
        return Rpc._manager.message(READY_MSG, interfaces)

    @staticmethod
    def notifyIpChange():
        if Rpc._manager is None:  # Not managed
            return None
        interfaces = ','.join([ v['mac'] + '=' + v['ip'] for v in net.getExternalIpAndMacs().values() ])
        return Rpc._manager.message(IP_MSG, interfaces)

    @staticmethod
    def resetId():
        logger.debug('Reseting rpc id')
        Rpc._manager._id = None

