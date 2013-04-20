package es.virtualcable.nx;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Hashtable;
import java.util.UUID;

// Adapted to Mac OS X Lion by Virginio

public class MacApplet implements OsApplet {
	
	private final String[] paths = { "/Applications/OpenNX/OpenNX.app/Contents/MacOS/" };
	private final String app = "OpenNXapp";
	
	private Hashtable<String,String> params;
	private String tmpDir = "";
	private String baseUrl = "";
	private String nxFileName = "";
	private String scrWidth;
	private String scrHeight;
	private String msg;

	public void start() {
		tmpDir  = System.getProperty("java.io.tmpdir") + File.separator;
		nxFileName  = tmpDir + UUID.randomUUID().toString() + ".nxs";			
		
		String width = params.get("width");
		String height = params.get("height");
		boolean fullScreen = false;
	
		// Notifies to broker the hostname/ip
		util.notifyHostname(baseUrl, params.get("is"));
		
		if( width.equals("-1"))
		{
			width = scrWidth;
			height = scrHeight;
			fullScreen = true;
		}
		
		NxFile nx = new NxFile(fullScreen, width, height);
		nx.host = params.get("ip");
		nx.username = params.get("user");
		nx.password = params.get("pass");
		nx.cachedisk = params.get("cacheDisk");
		nx.cachemem = params.get("cacheMem");
		nx.port = params.get("port");
		nx.desktop = params.get("session");
		nx.linkSpeed = params.get("connection");
		
		try {
			nx.saveFile( nxFileName );
		} catch (IOException e) {
			javax.swing.JOptionPane.showMessageDialog(null, "Can't save nx temporal file: " + e.getMessage());
			e.printStackTrace();
			msg = "DISK_WRITE_ERROR";
			return;
		}
		
		String execPath = "";
		
		for(int i = 0; i < paths.length; i++ )
		{
			File f = new File(paths[i] + app);
			if( f.exists() )
			{
				execPath = paths[i] + app;
				break;
			}
		}
		
		if( execPath.length() == 0 ) 
		{
			javax.swing.JOptionPane.showMessageDialog(null, "Can't find OpenNX. Install it from http://opennx.net/");
			System.err.println("Can't find OpenNX executable");
			msg = "PROGRAM_NOT_FOUND";
			return;
		}
		
		ArrayList<String> exec = new ArrayList<String>();
		exec.add(execPath);
		exec.add("--session=" + nxFileName);
		exec.add("--autologin");
		exec.add("--killerrors");
		
		try {
			ProcessBuilder pb = new ProcessBuilder(exec);
			pb.start();
		} catch(Exception e) {
			javax.swing.JOptionPane.showMessageDialog(null,"Exception at applet:\n" + e.getMessage());
			e.printStackTrace();
			msg = "APPLET_ERROR";
			return;
		}
	}

	public void init() {
	}

	public void destroy() {
		// TODO Auto-generated method stub

	}

	public void setParameters(Hashtable<String, String> parameters, String urlBase, 
			int screenWidth, int screenHeight) {
		params = parameters;
		baseUrl = urlBase;
		scrWidth = Integer.toString(screenWidth);
		scrHeight = Integer.toString(screenHeight);		
	}

	public String getMessage() {
		return msg;
	}

}
