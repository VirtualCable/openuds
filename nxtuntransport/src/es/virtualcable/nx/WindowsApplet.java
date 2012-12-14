package es.virtualcable.nx;

import java.io.File;
import java.io.IOException;
import java.util.Hashtable;
import java.util.Map;
import java.util.UUID;

import es.virtualcable.nx.FreePortFinder;
import es.virtualcable.nx.util;
import es.virtualcable.windows.WinRegistry;

public class WindowsApplet implements OsApplet {

	private Hashtable<String,String> params;
	private String tmpDir = "";
	private String baseUrl = "";
	private String nxFileName = "";
	private String jarFileName = "";
	private String scrWidth;
	private String scrHeight;
	private String tunPort = "";
	
	
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
			nxFileName  = tmpDir  + UUID.randomUUID().toString() + ".nxs";			
			jarFileName  = tmpDir + UUID.randomUUID().toString() + ".jar";
			
			// Notifies to broker the hostname/ip
			util.notifyHostname(baseUrl, params.get("is"));
			
			String width = params.get("width");
			String height = params.get("height");
			boolean fullScreen = false;
		
			if( width.equals("-1"))
			{
				width = scrWidth;
				height = scrHeight;
				fullScreen = true;
			}
			
			if( downloadJar()  == false)
				return;
			tunPort = Integer.toString(FreePortFinder.findFreePort());
			
			NxFile nx = new NxFile(fullScreen, width, height);
			nx.host = "127.0.0.1";
			nx.port = tunPort;
			nx.username = params.get("user");
			nx.password = params.get("pass");
			nx.cachedisk = params.get("cacheDisk");
			nx.cachemem = params.get("cacheMem");
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
				System.out.println(nxFileName);
				cmd = cmd.replaceAll("%1", nxFileName);
				executeTunnel(cmd);

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
	
	private void executeTunnel(String nxCmd) throws IOException
	{
		String java = System.getProperty("java.home") + File.separator + "bin" + File.separator + "java.exe";
		String cmd = "\"" + java + "\" -jar " + jarFileName + " " + tunPort + " " + nxCmd;
		ProcessBuilder pb = new ProcessBuilder( cmd );
		Map<String,String> env = pb.environment();
		env.put("TPARAMS", params.get("tun"));
		System.out.println("TPARAMS: " + params.get("tun"));
		System.out.println(cmd);
		pb.start();
		
	}
	
	private boolean downloadJar()
	{
		return util.download(baseUrl, "2", jarFileName);
	}
	
}
