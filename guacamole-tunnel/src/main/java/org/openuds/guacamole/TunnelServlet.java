package org.openuds.guacamole;

import java.io.BufferedReader;
import java.io.FileReader;
import java.net.URL;
import java.util.Arrays;
import java.util.Enumeration;
import java.util.Hashtable;
import java.util.Properties;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpSession;

import org.glyptodon.guacamole.GuacamoleException;
import org.glyptodon.guacamole.net.GuacamoleSocket;
import org.glyptodon.guacamole.net.GuacamoleTunnel;
import org.glyptodon.guacamole.net.InetGuacamoleSocket;
import org.glyptodon.guacamole.protocol.ConfiguredGuacamoleSocket;
import org.glyptodon.guacamole.protocol.GuacamoleClientInformation;
import org.glyptodon.guacamole.protocol.GuacamoleConfiguration;
import org.glyptodon.guacamole.servlet.GuacamoleHTTPTunnelServlet;
import org.glyptodon.guacamole.servlet.GuacamoleSession;

public class TunnelServlet
    extends GuacamoleHTTPTunnelServlet {

    /**
	 * 
	 */
	private static final long serialVersionUID = 2010742981126080080L;
	private static final String UDS_PATH = "/guacamole/";
	private static final String UDSFILE = "udsfile";
	private static final String UDS = "uds";
	
	
	private static Properties config = null;
	
	private String getConfigValue(String value) throws GuacamoleException {
		if( config == null ) {
			try {
				config = new Properties();
				config.load(getServletContext().getResourceAsStream("/WEB-INF/tunnel.properties"));
				if( null != config.getProperty(UDSFILE)) {
					
					BufferedReader bufferedReader = new BufferedReader(new FileReader(config.getProperty(UDSFILE)));
					URL u = new URL(bufferedReader.readLine());
					String uds = u.getProtocol() + "://" + u.getAuthority();
					bufferedReader.close();
					
					config.put(UDS, uds);
				}
					
			} catch( Exception e ) {
				throw new GuacamoleException(e.getMessage(), e);
			}
		}
		System.out.println("Getting value of " + value + ": " + config.getProperty(value));
		
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
    	
		Hashtable<String,String> params = Util.readParameters( getConfigValue(UDS) + UDS_PATH + data);
		
		if( params == null ) {
			System.out.println("Invalid credentials");
			throw new GuacamoleException("Can't access required user credentials");
		}
		
        System.out.println("Got parameters from remote server: " + data + ", " + width + "x" + height);
		
		GuacamoleClientInformation info = new GuacamoleClientInformation();
		info.setOptimalScreenWidth(Integer.parseInt(width));
		info.setOptimalScreenHeight(Integer.parseInt(height));
		
		System.out.println("Optiomal size: " + width + "x" + height);
		
		// Add audio mimetypes
        String[] audio_mimetypes = request.getParameterValues("audio");
        if (audio_mimetypes != null)
            info.getAudioMimetypes().addAll(Arrays.asList(audio_mimetypes));
        
        // Add video mimetypes
        String[] video_mimetypes = request.getParameterValues("video");
        if (video_mimetypes != null)
            info.getVideoMimetypes().addAll(Arrays.asList(video_mimetypes));       
    	
        // Create our configuration
        GuacamoleConfiguration config = new GuacamoleConfiguration();
        config.setProtocol(params.get("protocol"));
        
        System.out.println("Parsing parameters");
        
        Enumeration<String> keys = params.keys();
        while( keys.hasMoreElements() ) {
        	String key = keys.nextElement();
        	if( "protocol".equals(key) )
        		continue;
        	System.out.println("Parameter " + key + ": " + params.get(key));
        	config.setParameter(key, params.get(key));
        }
        
        System.out.println("Opening soket");
        
        // Connect to guacd - everything is hard-coded here.
        GuacamoleSocket socket = null;
        try {
	        socket = new ConfiguredGuacamoleSocket(
	                new InetGuacamoleSocket("127.0.0.1", 4822),
	                config, info
	        );
        } catch( Exception e ) {
        	System.out.print(e.getMessage());
        	System.out.print(e);
        }
        
        System.out.println("Initializing socket " + socket.toString());

        // Establish the tunnel using the connected socket
        GuacamoleTunnel tunnel = new GuacamoleTunnel(socket);

        System.out.println("Initializing tunnel " + tunnel.toString());
        
        // Attach tunnel to session
        HttpSession httpSession = request.getSession(true);
        GuacamoleSession session = new GuacamoleSession(httpSession);
        session.attachTunnel(tunnel);
        
        System.out.println("Returning tunnel");

        // Return pre-attached tunnel
        return tunnel;

    }
	
}