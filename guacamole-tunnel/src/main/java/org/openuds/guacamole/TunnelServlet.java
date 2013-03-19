package org.openuds.guacamole;

import java.util.Enumeration;
import java.util.Hashtable;
import java.util.Properties;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpSession;
import net.sourceforge.guacamole.GuacamoleException;
import net.sourceforge.guacamole.net.GuacamoleSocket;
import net.sourceforge.guacamole.net.GuacamoleTunnel;
import net.sourceforge.guacamole.net.InetGuacamoleSocket;
import net.sourceforge.guacamole.protocol.ConfiguredGuacamoleSocket;
import net.sourceforge.guacamole.protocol.GuacamoleClientInformation;
import net.sourceforge.guacamole.protocol.GuacamoleConfiguration;
import net.sourceforge.guacamole.servlet.GuacamoleHTTPTunnelServlet;
import net.sourceforge.guacamole.servlet.GuacamoleSession;

public class TunnelServlet
    extends GuacamoleHTTPTunnelServlet {

    /**
	 * 
	 */
	private static final long serialVersionUID = 2010742981126080080L;
	private static final String UDS_PATH = "/guacamole/";
	
	
	private static Properties config = null;
	
	private String getConfigValue(String value) throws GuacamoleException {
		if( config == null ) {
			try {
				config = new Properties();
				config.load(getServletContext().getResourceAsStream("/WEB-INF/tunnel.properties"));
			} catch( Exception e ) {
				throw new GuacamoleException(e.getMessage(), e);
			}
		}
		
		return config.getProperty(value);
			
	}
	
	@Override
    protected GuacamoleTunnel doConnect(HttpServletRequest request)
        throws GuacamoleException {
    	
    	String data = request.getParameter("data");
    	String width = request.getParameter("width");
    	String height = request.getParameter("height");
    	
    	if( data == null || width == null || height == null)
    		throw new GuacamoleException("Can't read required parameters");
    	
    	
		Hashtable<String,String> params = Util.readParameters( getConfigValue("uds") + UDS_PATH + data);
		
		if( params == null ) {
			System.out.println("Invalid credentials");
			throw new GuacamoleException("Can't access required user credentials");
		}
		
		GuacamoleClientInformation info = new GuacamoleClientInformation();
		info.setOptimalScreenWidth(Integer.parseInt(width));
		info.setOptimalScreenHeight(Integer.parseInt(height));
    	
        // Create our configuration
        GuacamoleConfiguration config = new GuacamoleConfiguration();
        config.setProtocol(params.get("protocol"));
        
        
        Enumeration<String> keys = params.keys();
        while( keys.hasMoreElements() ) {
        	String key = keys.nextElement();
        	if( "protocol".equals(key) )
        		continue;
        	config.setParameter(key, params.get(key));
        }
        
        
        //config.setParameter("hostname", "w7adolfo");
        //config.setParameter("username", "admin");
        //config.setParameter("password", "temporal");

        // Connect to guacd - everything is hard-coded here.
        GuacamoleSocket socket = new ConfiguredGuacamoleSocket(
                new InetGuacamoleSocket("localhost", 4822),
                config, info
        );

        // Establish the tunnel using the connected socket
        GuacamoleTunnel tunnel = new GuacamoleTunnel(socket);

        // Attach tunnel to session
        HttpSession httpSession = request.getSession(true);
        GuacamoleSession session = new GuacamoleSession(httpSession);
        session.attachTunnel(tunnel);

        // Return pre-attached tunnel
        return tunnel;

    }
	
}