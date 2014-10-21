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
    import socket
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

if __name__ == '__main__':
    ipcTest()

