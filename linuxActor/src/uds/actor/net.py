'''
@author: Ben Mackey (getHwAddr) and paul cannon (getIpAddr)
@see: http://code.activestate.com/recipes/439094-get-the-ip-address-associated-with-a-network-inter/
'''
import fcntl, socket, struct, array, platform

import logging
logger = logging.getLogger(__name__)


def getMacAddr(ifname):
    if isinstance(ifname, list):
        return dict([ (name, getMacAddr(name)) for name in ifname ])
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', ifname[:15]))
        return ''.join(['%02x:' % ord(char) for char in info[18:24]])[:-1]
    except Exception:
        return None

def getIpAddr(ifname):
    if isinstance(ifname, list):
        return dict([ (name, getIpAddr(name)) for name in ifname ])
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', ifname[:15])
        )[20:24])
    except Exception:
        return None

def getInterfaces():
    max_possible = 128  # arbitrary. raise if needed.
    space = max_possible * 16
    if platform.architecture()[0] == '32bit':
        offset, length = 32, 32
    elif platform.architecture()[0] == '64bit':
        offset, length = 16, 40
    else:
        raise OSError('Unknown arquitecture {0}'.format(platform.architecture()[0]))

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    names = array.array('B', '\0' * space)
    outbytes = struct.unpack('iL', fcntl.ioctl(
        s.fileno(),
        0x8912,  # SIOCGIFCONF
        struct.pack('iL', space, names.buffer_info()[0])
    ))[0]
    namestr = names.tostring()
    return [namestr[i:i + offset].split('\0', 1)[0] for i in range(0, outbytes, length)]

def getIpAndMac(ifname):
    ip, mac = getIpAddr(ifname), getMacAddr(ifname)
    if isinstance(ifname, list):
        return dict([ (key, { 'ip': ip[key], 'mac': mac[key] }) for key in ip.keys() ])
    return (ip, mac)

def getExternalIpAndMacs():
    res = getIpAndMac(getInterfaces())
    logger.debug('Res: {0}'.format(res))
    for key in res.keys():
        if res[key]['mac'] == '00:00:00:00:00:00':
            del res[key]
    return res

