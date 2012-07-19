package es.virtualcable.nx;

import java.io.File;
import java.io.IOException;
import java.util.Hashtable;
import java.util.Map;
import java.util.UUID;


public class MacApplet implements OsApplet {

	private final String[] paths = { "/Applications/NX Client for OSX.app/Contents/MacOS/" };
	private final String nxclient = "nxclient";

	private Hashtable<String,String> params;
	private String tmpDir = "";
	private String baseUrl = "";
	private String nxFileName = "";
	private String jarFileName = "";
	private String scrWidth;
	private String scrHeight;
	private String tunPort = "";

	public void start() {
		try {
		tmpDir  = System.getProperty("java.io.tmpdir") + File.separator;
		nxFileName  = tmpDir  + UUID.randomUUID().toString() + ".nxs";			
		jarFileName  = tmpDir + UUID.randomUUID().toString() + ".jar";
		
		//System.out.println(nxFileName);
		
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
		
		String execPath = "";
		
		for(int i = 0; i < paths.length; i++ )
		{
			File f = new File(paths[i] + nxclient);
			if( f.exists() )
			{
				execPath = paths[i] + nxclient;
				break;
			}
		}

		if( execPath.length() == 0 ) 
		{
			javax.swing.JOptionPane.showMessageDialog(null, "Can't find nxclient client.\nShould be at /Applications/NX Client for OSX.app/Contents/MacOS/\nPlease, install it");
			System.err.println("Can't find nxclient.");
			return;
		}
		
		executeTunnel(execPath);
		
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
		String java = System.getProperty("java.home") + File.separator + "bin" + File.separator + "java";
		String [] exec = { java, "-jar", jarFileName, tunPort, nxCmd, "--session", nxFileName }; 
		ProcessBuilder pb = new ProcessBuilder( exec );
		Map<String,String> env = pb.environment();
		env.put("TPARAMS", params.get("tun"));
		System.out.println("TPARAMS: " + params.get("tun"));
		for (String str : exec) {
			System.out.print(str + " ");
		}
		System.out.println();
		pb.start();
		
	}
	
	public void setParameters(Hashtable<String, String> parameters, String urlBase, 
			int screenWidth, int screenHeight) {
		params = parameters;
		baseUrl = urlBase;
		scrWidth = Integer.toString(screenWidth);
		scrHeight = Integer.toString(screenHeight);		
		
	}
	
	private boolean downloadJar()
	{
		return util.download(baseUrl, "2", jarFileName);
	}
	

}
