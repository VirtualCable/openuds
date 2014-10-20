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
    from udsactor import ipc_server
    import socket
    from time import sleep

    s = ipc_server.ServerIPC(39188)  # I have got the enterprise number for Virtual Cable. This number is not about ports, but as good as any other selection :)

    s.start()

    counter = 0
    while counter < 4:
        counter += 1
        so = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        so.connect(('localhost', 39188))
        sleep(1)
        s.sendMessage(ipc_server.MSG_LOGOFF, None)
        print so.recv(512)
        s.sendMessage(ipc_server.MSG_MESSAGE, 'Cierra la sesión')
        print so.recv(512)

        so.close()
        sleep(1)

    s.stop()
    s.join()


if __name__ == '__main__':
    ipcTest()

