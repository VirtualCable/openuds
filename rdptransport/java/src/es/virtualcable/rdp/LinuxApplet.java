package es.virtualcable.rdp;

import java.io.File;
import java.util.ArrayList;
import java.util.Hashtable;
import java.util.Map;
import java.util.UUID;

public class LinuxApplet implements OsApplet {
	private final String[] paths = { "/usr/local/bin/", "/usr/bin/" };
	private final String rdesktop = "rdesktop";
	
	private Hashtable<String,String> params;
	private String jarFileName = "";
	private String tmpDir = "";
	private String baseUrl = "";
	private String tunPort = "";
	
	private void addParameterIfNotEmpty(ArrayList<String> exec, String param, String value)
	{
		if( value.length() == 0 )
			return;
		if( param.indexOf(' ') != -1 )
			exec.add( param + "\"" + value + "\"");
		else
			exec.add(param + value);
	}

	public void start() {
		try {
			String colors = params.get("c");
			String width = params.get("w");
			String height = params.get("h");
			String server = params.get("s"); // Server
			String user = params.get("u"); // User
			String password = params.get("p"); // password
			String domain = params.get("d"); // domain
			
			tmpDir  = System.getProperty("java.io.tmpdir") + File.separator;
			jarFileName  = tmpDir + UUID.randomUUID().toString() + ".jar";
			
			boolean redirectSmartcards = params.get("sc").equals("1");
			boolean redirectDrives = params.get("dr").equals("1");
			boolean redirectSerials = params.get("se").equals("1");
			boolean redirectPrinters = params.get("pr").equals("1");
			boolean redirectAudio = params.get("au").equals("1");
			boolean compression = params.get("cr").equals("1");
			
			String home = System.getProperty("user.home");

			ArrayList<String> exec = new ArrayList<String>();
			
			if(params.get("tun") != null)
			{
				if( downloadJar()  == false)
					return;
				tunPort = Integer.toString(FreePortFinder.findFreePort());
				server = "localhost:" + tunPort;
				String java = System.getProperty("java.home") + File.separator + "bin" + File.separator + "java";
				exec.add(java);	exec.add("-jar"); exec.add(jarFileName); exec.add(tunPort);
			}

			String execPath = "";
			
			for(int i = 0; i < paths.length; i++ )
			{
				File f = new File(paths[i] + rdesktop);
				if( f.exists() )
				{
					execPath = paths[i] + rdesktop;
					break;
				}
			}
			
			if( execPath.length() == 0 ) 
			{
				javax.swing.JOptionPane.showMessageDialog(null, "Can't find rdesktop client.\nShould be at /usr/bin or /usr/local/bin\nPlease, install it");
				return;
			}
			
			exec.add(execPath);
			
			addParameterIfNotEmpty(exec, "-u", user);
			addParameterIfNotEmpty(exec, "-d", domain);
			if( password.length() != 0 )
				exec.add("-p-");
			addParameterIfNotEmpty(exec, "-a", colors);
			if( width.equals("-1") )
				exec.add("-f");
			else
				exec.add("-g" + width + "x" + height);
			
			exec.add("-TUDS-RDP");
			exec.add("-P");
			
			if( redirectSmartcards )
			{
			}
			
			if( compression )
			{
				exec.add("-z");
			}
			
			if( redirectDrives )
				exec.add("-rdisk:home=\"" + home + "\"");
			
			if( redirectAudio )
				exec.add("-rsound:local");
			else
				exec.add("-rsound:off");
			
			if( redirectSerials )
				exec.add("-rcomport:COM1=/dev/ttyS0");
			
			if( redirectPrinters ) // Will have to look at local cups to find printer 
			{
			}
			
			exec.add(server);
			
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
