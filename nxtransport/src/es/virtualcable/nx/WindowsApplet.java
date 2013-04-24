package es.virtualcable.nx;

import java.io.File;
import java.io.IOException;
import java.util.Hashtable;
import java.util.UUID;

import es.virtualcable.windows.WinRegistry;

public class WindowsApplet implements OsApplet {

	private Hashtable<String,String> params;
	private String tmpDir = "";
	private String baseUrl = "";
	private String nxFileName = "";
	private String scrWidth;
	private String scrHeight;
	
	public void setParameters(Hashtable<String, String> parameters, String urlBase, 
			int screenWidth, int screenHeight) {
		params = parameters;
		baseUrl = urlBase;
		scrWidth = Integer.toString(screenWidth);
		scrHeight = Integer.toString(screenHeight);		
	}

	public void start() {
		try {
			tmpDir  = System.getProperty("java.io.tmpdir") + File.separator;
			System.out.println(tmpDir);
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
				return;
			}

			String cmd = WinRegistry.readString(WinRegistry.HKEY_CURRENT_USER, "Software\\Classes\\NXClient.session\\shell\\open\\command", "");
			if ( null == cmd )
				javax.swing.JOptionPane.showMessageDialog(null, "Can't find Nomachine client. Please, install it");
			else
			{
				nxFileName = nxFileName.replace("\\", "\\\\");
				cmd = cmd.replaceAll("%1", nxFileName);
				ProcessBuilder pb = new ProcessBuilder(util.splitCommandLine(cmd));
				pb.start();
			}
		} catch (Exception e) {
			javax.swing.JOptionPane.showMessageDialog(null,"Exception at applet:\n" + e.getMessage());
			e.printStackTrace();
			return;
		}
	}

	public void init() {
	}

	public void destroy() {
	}
	
}
