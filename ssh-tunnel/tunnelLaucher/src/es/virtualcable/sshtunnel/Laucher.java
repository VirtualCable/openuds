/**
 * 
 */
package es.virtualcable.sshtunnel;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.UnsupportedEncodingException;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.Map;


import com.jcraft.jsch.*;

/**
 * @author dkmaster
 *
 */

public class Laucher {

	private static final String ENV_PARAMS = "TPARAMS";
	private static final String ENV_LISTEN = "TLISTEN";
	
	public static long allowConnectionsForTime = -1; 
	/**
	 * @param args
	 */
	public static void main(String[] args) {
		
		// Environment variable TPARAMS contains, separated by spaces:
		// 1º user for SSH server 
		// 2º password for SSH server
		// 3º remote ssh host
		// 4º remote ssh port
		// 5º remote redirected host
		// 6º remote redirected port
		// 7º If != 0, uses compression specified (1-9) (server to client), do not use else
		// 8º (optional). Indicates the number of seconds to allow new incoming connections to tunneler
		// Arguments needed:
		// 1º local listening port (always at localhost)
		// 2º and next: remote command & params
		if( args.length < 1 || System.getenv(ENV_PARAMS) == null )
		{
			System.err.println("Need all parameters and " + ENV_PARAMS + " environment var.");
			return;  // Can't exec without all params
		}
		
		String params[] = System.getenv(ENV_PARAMS).split(" ");
		if( params.length < 7 )
		{
			System.err.println( ENV_PARAMS + " environment variable seems incorrect.");
			return;
		}
		
		String user;
		String pass;
		try {
			user = java.net.URLDecoder.decode(params[0], "UTF-8");
			pass = java.net.URLDecoder.decode(params[1], "UTF-8");
		} catch (UnsupportedEncodingException e) {
			System.err.println("Caugth exception: " + e);
			return;
		}
		String remoteServer = params[2];
		int remotePort = Integer.parseInt(params[3]);
		String targetHost = params[4];
		int targetPort = Integer.parseInt(params[5]);
		String compressionLevel = params[6];
		if( params.length == 8 )
		{
			allowConnectionsForTime = Long.parseLong(params[7]);
			System.out.println("Allow connections for a while " + allowConnectionsForTime);
		}
			
		int localPort = Integer.parseInt(args[0]);

		String[] cmdArray = new String[args.length-1];
		
		for(int i = 1; i < args.length; i++ )
			cmdArray[i-1] = args[i];
		
		JSch jsch = new JSch();
		Session session = null;
		try {
			session = jsch.getSession(user, remoteServer, remotePort);
			session.setUserInfo(new PassProvider(pass));
			if( !compressionLevel.equals("0") )
			{
				System.out.println("Using compression");
				session.setConfig("compression.s2c", "zlib@openssh.com,zlib,none");
			    session.setConfig("compression.c2s", "none");
			    session.setConfig("compression_level", compressionLevel);
			}
			else
			{
				System.out.println("No compression used");
				session.setConfig("compression.s2c", "none");
			    session.setConfig("compression.c2s", "none");				
			}
			
			session.connect();
			
			session.setPortForwardingL("127.0.0.1", localPort, targetHost, targetPort, new SSFactory());
			System.out.println("Listening at " + localPort);
			
			/*// Used for debugging
			  FileOutputStream out = new FileOutputStream("/tmp/out.txt");
			
			
			for(String s: cmdArray) {
				out.write( s.getBytes() );
				out.write( '\n' );
			}*/
			try {
				// We will copy input stream to forked child
				ProcessBuilder pb = new ProcessBuilder(cmdArray);
				Map<String,String> env = pb.environment();
				// Remove variables
				env.remove(ENV_PARAMS);
				env.put(ENV_LISTEN, Integer.toString(localPort));
				
				Process p = pb.start();
				pipein(System.in, p.getOutputStream());
				pipe(p.getErrorStream(), System.out);
				pipe(p.getInputStream(), System.err);
				//p.waitFor();
				//System.out.println(p.exitValue());
			} catch (IOException e) {
				System.out.println(e);
			}
			// We will wait max of 30 seconds for a connection to tunnel, if not used in that interval, it will get closed
			// And program will finish
			int counter = 30;
			while( SerSocket.socket == null && --counter > 0) {
				Thread.sleep(1000);
			}
			if( counter <= 0 )
			{
				System.out.println("Connection timed out");
				javax.swing.JOptionPane.showMessageDialog(null, "Tunneled expired (client not connected)");				
				throw new InterruptedException("Connection timed out");
			}
			System.out.println("Tunnel connected");
			// Now we wait for tunnel closing
			while( SerSocket.socket.isClosed() == false )
				Thread.sleep(1000);
			System.out.println("Tunnel disconnected");
			session.disconnect();
			
		} catch (JSchException e) {
			javax.swing.JOptionPane.showMessageDialog(null, "Can't contact remote tunneler server:" + remoteServer + ":" + remotePort);			
			System.err.println(e);
		} catch (InterruptedException e) {
			if( session.isConnected() )
				session.disconnect();
			System.err.println(e);
		} catch( Exception e ) {
			if( session.isConnected() )
				session.disconnect();
			System.err.println(e);
		}
		
		System.exit(0);
	}

	public static class PassProvider implements UserInfo {

		private String pass;
		
		PassProvider(String password)
		{
			super();
			this.pass = password;
		}
		
		@Override
		public String getPassphrase() {
			return null;
		}

		@Override
		public String getPassword() {
			return this.pass;
		}

		@Override
		public boolean promptPassphrase(String arg0) {
			return true;
		}

		@Override
		public boolean promptPassword(String arg0) {
			return true;
		}

		@Override
		public boolean promptYesNo(String arg0) {
			return true;
		}

		@Override
		public void showMessage(String arg0) {
			System.out.println(arg0);
			
		}
		  
	  }
	
	private static void pipein(final InputStream src, final OutputStream dest) {

	    new Thread(new Runnable() {
	        public void run() {
	            try {
	               int ret = -1;
	               while ((ret = src.read()) != -1) {
	                  dest.write(ret);
	                  dest.flush();
	               }
	            } catch (IOException e) { // just exit
	            }
	        }
	    }).start();

	}
	
	private static void pipe(final InputStream src, final OutputStream dest) {
	    new Thread(new Runnable() {
	        public void run() {
	            try {
	                byte[] buffer = new byte[1024];
	                for (int n = 0; n != -1; n = src.read(buffer)) {
	                    dest.write(buffer, 0, n);
	                }
	            } catch (IOException e) { // just exit
	            }
	        }
	    }).start();
	}
	
	
	private static class SerSocket extends ServerSocket {

		public static Socket socket = null;
		public static long firstConnectionTime; 
		
		public SerSocket(int port, int backlog, InetAddress bindAddr)
				throws IOException {
			super(port, backlog, bindAddr);
		}
		
		@Override
		public Socket accept() throws IOException
		{
			while( true )
			{
				Socket so = super.accept();
				if( socket ==  null )
				{
					socket = so;
					firstConnectionTime = System.currentTimeMillis();
				}
				else
				{
					if( Laucher.allowConnectionsForTime == -1 )
					{
						so.close();  // Second connections not allowed
						continue;
					}
					
					if( (System.currentTimeMillis() - firstConnectionTime) > Laucher.allowConnectionsForTime*1000)
					{
						System.out.println("No se permiten mas conexiones");
						so.close();
						continue;
					}
					
					// Allow connection, but keep an eye on first connection
				}
				
				return so;
			}
		}
		
	}

	private static class SSFactory implements ServerSocketFactory {

		@Override
		public ServerSocket createServerSocket(int port, int backlog,
				InetAddress bindAddr) throws IOException {
			return new SerSocket(port, backlog, bindAddr);
		}
		
	}
}
