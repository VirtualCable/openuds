# -*- coding: utf-8 -*-
from __future__ import unicode_literals


def testRest():
    from udsactor import operations
    from udsactor import store
    from udsactor import REST

    cfg = store.readConfig()
    print cfg
    print "Intefaces: ", list(operations.getNetworkInfo())
    print "Joined Domain: ", operations.getDomainName()

    #renameComputer('win7-64')
    #joinDomain('dom.dkmon.com', 'ou=pruebas_2,dc=dom,dc=dkmon,dc=com', 'administrador@dom.dkmon.com', 'Temporal2012', True)
    #reboot()
    r = REST.Api(cfg['host'], cfg['masterKey'], cfg['ssl'], scrambledResponses=True)
    print "Connected: {}".format(r.isConnected)
    r.test()
    try:
        r.init('02:46:00:00:00:07')
    except REST.UnmanagedHostError:
        print 'Unmanaged host (confirmed)'

    uuid = r.init('02:46:00:00:00:08')
    print "Notify comm:", r.notifyComm('http://172.27.0.1:8000/')

    print "Connected: {}".format(r.isConnected)

    print 'uuid = {}'.format(uuid)

    #print 'Login: {}'.format(r.login('test-user'))
    #print 'Logout: {}'.format(r.logout('test-user'))
    print "Information: >>{}<<".format(r.information())
    print "Login: >>{}<<".format(r.login('Pepito'))

    print r.setReady([(v.mac, v.ip) for v in operations.getNetworkInfo()])
    print r.log(10000, 'Test error message')

def ipcTest():
    from udsactor import ipc
    from time import sleep

    s = ipc.ServerIPC(39188)  # I have got the enterprise number for Virtual Cable. This number is not about ports, but as good as any other selection :)

    s.start()

    client = ipc.ClientIPC(39188)
    client.start()
    client2 = ipc.ClientIPC(39188)
    client2.start()

    sleep(1)

    s.sendMessage(ipc.MSG_LOGOFF, None)
    s.sendMessage(ipc.MSG_MESSAGE, 'Cierra la sesión')
    s.sendMessage(33, 'invalid')
    s.sendMessage(ipc.MSG_SCRIPT, 'print "hello"')

    for c in (client, client2):
        print c.getMessage()
        print c.getMessage()
        print c.getMessage()

    client.stop()
    client.join()

    s.sendMessage(ipc.MSG_LOGOFF, None)
    s.sendMessage(ipc.MSG_MESSAGE, 'Cierra la sesión')
    s.sendMessage(33, 'invalid')
    s.sendMessage(ipc.MSG_SCRIPT, 'print "hello"')

    print client2.getMessage()
    print client2.getMessage()
    print client2.getMessage()

    client2.stop()
    s.stop()
    client2.join()
    s.join()

def ipcServer():
    from udsactor import ipc
    from win32api import Sleep

    s = ipc.ServerIPC(39188, {'idle': 180})  # I have got the enterprise number for Virtual Cable. This number is not about ports, but as good as any other selection :)

    s.start()


    counter = 0
    while True:
        try:
            counter += 1
            print "Sending new message {}".format(counter)
            s.sendMessage(ipc.MSG_MESSAGE, 'This is a test message ñöitó 33.3€ {}'.format(counter))
            counter += 1
            s.sendMessage(ipc.MSG_SCRIPT, 'print "This is a test message ñöitó 33.3€ {}"'.format(counter))
            counter += 1
            s.sendMessage(ipc.MSG_LOGOFF, None)
            Sleep(1000)
        except:
            break

    s.stop()

def testIdle():
    from udsactor import operations
    from win32api import Sleep

    for i in xrange(1, 10):
        print operations.getIdleDuration()
        Sleep(1000)

def testServer():
    from udsactor import httpserver
    from win32api import Sleep
    import random
    import requests
    import json

    while True:
        try:
            port = random.randrange(32000, 64000)
            server = httpserver.HTTPServerThread(('172.27.0.8', port))
            break
        except:
            pass

    serverUrl = server.getServerUrl()
    server.start()

    print serverUrl

    res = requests.post(serverUrl + '/message', data=json.dumps({'Data': 'test1', 'Other': 'test2'}), headers={'content-type': 'application/json'})
    print res
    print res.json()

    res = requests.get(serverUrl + '/information?param1=1&param2=2', headers={'content-type': 'application/json'})
    print res
    print res.json()

    #try:
    #    while True:
    #        Sleep(1000)
    #except:
    #    pass

    server.stop()
    server.join()


if __name__ == '__main__':
    #ipcServer()
    #testRest()
    #testIdle()
    testServer()

