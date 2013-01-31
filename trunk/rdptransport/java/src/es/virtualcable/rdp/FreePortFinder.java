package es.virtualcable.rdp;

import java.io.IOException;
import java.net.*;
import java.util.Random;


public class FreePortFinder {

	private final static int START_PORT = 35000;
	private final static int START_PORT_MAX = 44000;
	private final static int END_PORT = 45500;
	
	public static boolean isFree(int port)
	{
		boolean free = true;
		try {
			 InetAddress addr = InetAddress.getByName("localhost");
			 SocketAddress sa = new InetSocketAddress(addr, port);
			 ServerSocket socket = new ServerSocket();
			 socket.bind(sa);
			 socket.close();
		} catch (IOException e) {
			free = false;
		}
		return free;
	}
	
	public static int findFreePort()
	{
		Random rnd = new Random();
		int startPort = START_PORT + rnd.nextInt(START_PORT_MAX-START_PORT);
		for( int port = startPort; port < END_PORT; port ++)
		{
			if( isFree(port) )
				return port;
		}
		return -1;
	}
}
