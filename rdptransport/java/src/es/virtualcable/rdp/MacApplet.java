package es.virtualcable.rdp;

import java.io.File;
import java.util.ArrayList;
import java.util.Hashtable;
import java.util.Map;
import java.util.UUID;

public class MacApplet implements OsApplet {
	private final String[] paths = { "/usr/bin/" };
	private final String open = "open";
	private final String cordPath = "/Applications/CoRD.app/Contents/MacOS/CoRD";
	
	private Hashtable<String,String> params;
	private String jarFileName = "";
	private String tmpDir = "";
	private String baseUrl = "";
	private String tunPort = "";
	
	private String convSpaces(String value)
	{
		final String weird = "$#$_$#$";
		if( value == null || value.isEmpty())
			return "";
		String res = value.replaceAll(" ", "%20");
		res = res.replaceAll("&", weird);
		return res.replaceAll(weird, "&amp;");
	}
	
	private void Cord(ArrayList<String> exec, String user, String password, String server, 
			String domain, String colors, String width, String height, boolean redirectAudio, 
			boolean redirectSmartcards, boolean redirectDrives,
			boolean redirectSerials, boolean redirectPrinters)
	{
		String url = "rdp://";
		
		if(!user.isEmpty()) {
			url += user;
			if(!password.isEmpty())
				url += ":" + password;
			url += "@";
		}
		
		url += server + "/";
		if(!domain.isEmpty())
			url += domain;
		url += "?screenDepth=" + colors + "&";
		if(width.equals("-1"))
			url += "fullscreen=true";
		else
			url += "screenWidth="+width+"&screenHeight="+height;
		
		url += "&forwardAudio=";
		
		if( redirectAudio )
			url += "0";
		else
			url += "1";
		
		if( redirectSmartcards ) // Not supported by Cord
		{
		}
		
		if( redirectDrives )
			url += "&forwardDisks=true";
		
		if( redirectSerials )
		{
		}
		
		if( redirectPrinters )
			url += "&forwardPrinters=true";
		
		exec.add(url);
		
	}

	public void start() {
		try {
			String colors = params.get("c");
			String width = params.get("w");
			String height = params.get("h");
			String server = params.get("s"); // Server
			String user = convSpaces(params.get("u")); // User
			String password = convSpaces(params.get("p")); // password
			String domain = convSpaces(params.get("d")); // domain
			
			tmpDir  = System.getProperty("java.io.tmpdir") + File.separator;
			jarFileName  = tmpDir + UUID.randomUUID().toString() + ".jar";
			
			boolean redirectSmartcards = params.get("sc").equals("1");
			boolean redirectDrives = params.get("dr").equals("1");
			boolean redirectSerials = params.get("se").equals("1");
			boolean redirectPrinters = params.get("pr").equals("1");
			boolean redirectAudio = params.get("au").equals("1");
			//boolean compression = params.get("cr").equals("1");
			
			//String home = System.getProperty("user.home");

			ArrayList<String> exec = new ArrayList<String>();
			
			if(params.get("tun") != null)
			{
				if( downloadJar()  == false)
					return;
				tunPort = Integer.toString(FreePortFinder.findFreePort());
				server = "127.0.0.1:" + tunPort;
				String java = System.getProperty("java.home") + File.separator + "bin" + File.separator + "java";
				exec.add(java);	exec.add("-jar"); exec.add(jarFileName); exec.add(tunPort);
			}

			String execPath = "";
			
			for(int i = 0; i < paths.length; i++ )
			{
				File f = new File(paths[i] + open);
				if( f.exists() )
				{
					execPath = paths[i] + open;
					break;
				}
			}
			
			if(( new File(cordPath)).exists() == false )
			{
				javax.swing.JOptionPane.showMessageDialog(null, "Can't find CoRD client. Please, install it before proceeding.");
				return;
			}
			
			if( execPath.length() == 0 ) 
			{
				javax.swing.JOptionPane.showMessageDialog(null, "Can't find rdesktop client.\nShould be at /usr/bin or /usr/local/bin\nPlease, install it");
				return;
			}
			
			exec.add(execPath);
			
			Cord(exec, user, password, server, domain, colors, width, height, redirectAudio, redirectSmartcards,
					redirectDrives, redirectSerials, redirectPrinters);
			
/*			Iterator<String> it = exec.iterator();
			while( it.hasNext()) {
				System.out.print(it.next() + " ");
			}
			System.out.println();
*/			
			Process p;
			try {
				ProcessBuilder pb = new ProcessBuilder(exec);
				if( params.get("tun") != null)
				{
					Map<String,String> env = pb.environment();
					env.put("TPARAMS", params.get("tun"));
					//System.out.println("TPARAMS: " + params.get("tun"));
				}
				p = pb.start();
			} catch(Exception e) {
				javax.swing.JOptionPane.showMessageDialog(null,"Exception launching " + execPath + ":\n" + e.getMessage());
				e.printStackTrace();
				return;
			}
			
			if( password.length() != 0 )
			{
				try {
					p.getOutputStream().write(password.getBytes());
					p.getOutputStream().write( new byte[]{'\n'} );
					p.getOutputStream().flush();
				}
				catch( Exception e ) {
					javax.swing.JOptionPane.showMessageDialog(null,"Exception communicating with " + execPath + ":\n" + e.getMessage());
					return;
					
				}
			}
		}
		catch(Exception e)
		{
			javax.swing.JOptionPane.showMessageDialog(null,"Exception at applet:\n" + e.getMessage());
			e.printStackTrace();
			return;
		}
		

	}

	public void init() {

	}

	public void destroy() {

	}

	public void setParameters(Hashtable<String, String> parameters,
			String urlBase, int screenWidth, int screenHeight) {
		params = parameters;
		baseUrl = urlBase;
	}

	private boolean downloadJar()
	{
		return util.download(baseUrl, "3", jarFileName);
	}
	
}
