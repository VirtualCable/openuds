package es.virtualcable.rdp;

import java.io.File;
import java.io.IOException;
import java.util.Hashtable;
import java.util.Map;
import java.util.UUID;

import es.virtualcable.rdp.util;

public class WindowsApplet implements OsApplet {

	private static final String MSTSC_CMD = "c:\\windows\\system32\\mstsc.exe";
	
	private Hashtable<String,String> params;
	private String scrWidth;
	private String scrHeight;
	private String tmpDir = "";
	private String rdpFileName = "";
	private String dllFileName = "";
	private String jarFileName = "";
	private String baseUrl = "";
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
			rdpFileName  = tmpDir + UUID.randomUUID().toString() + ".tmp";
			dllFileName  = tmpDir + UUID.randomUUID().toString() + ".tmp";
			jarFileName  = tmpDir + UUID.randomUUID().toString() + ".jar";
			if( downloadDll() == false )
				return;
			
			if(params.get("tun") != null)
			{
				if( downloadJar()  == false)
					return;
				tunPort = Integer.toString(FreePortFinder.findFreePort());
			}
			
			System.load(dllFileName);
			
			String width = params.get("w");
			String height = params.get("h");
			boolean fullScreen = false;
		
			if( width.equals("-1"))
			{
				width = scrWidth;
				height = scrHeight;
				fullScreen = true;
			}
			
			WinRdpFile rdp = new WinRdpFile(fullScreen, width, height, params.get("c"));
			if( params.get("tun") != null )
			{
				rdp.address = "127.0.0.1:" + tunPort;
			}
			else
				rdp.address = params.get("s"); // Server
			rdp.username = params.get("u"); // User
			rdp.password = params.get("p"); // password
			rdp.domain = params.get("d"); // domain
			rdp.redirectSmartcards = params.get("sc").equals("1");
			rdp.redirectDrives = params.get("dr").equals("1");
			rdp.redirectSerials = params.get("se").equals("1");
			rdp.redirectPrinters = params.get("pr").equals("1");
			rdp.redirectAudio = params.get("au").equals("1");
			rdp.compression = params.get("cr").equals("1");
			
			try {
				rdp.saveFile( rdpFileName );
				if( params.get("tun") != null )
					executeTunnel();
				else
					executeDirect();
				
			} catch (IOException e) {
				e.printStackTrace();
				return;
			}

			// Process p =
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
	
	private void executeTunnel() throws IOException
	{
		String java = System.getProperty("java.home") + File.separator + "bin" + File.separator + "java.exe";
		String [] cmd = { java, "-jar", jarFileName, tunPort, MSTSC_CMD, rdpFileName };  
		ProcessBuilder pb = new ProcessBuilder( cmd );
		Map<String,String> env = pb.environment();
		env.put("TPARAMS", params.get("tun"));
		//System.out.println("TPARAMS: " + params.get("tun"));
		//System.out.println("java: " + java + " -jar " + jarFileName + " " + MSTSC_CMD + " " + rdpFileName);
		pb.start();
		
	}
	
	private void executeDirect() throws IOException
	{
		Runtime.getRuntime().exec( MSTSC_CMD + " \"" + rdpFileName + "\"" );
	}
	
	private boolean downloadDll()
	{
		return util.download(baseUrl, "2", dllFileName);
	}
	
	private boolean downloadJar()
	{
		return util.download(baseUrl, "3", jarFileName);
	}

}
