
import java.applet.*;
import java.awt.*;
import java.security.AccessController;
import java.security.PrivilegedAction;
import java.util.Hashtable;
import es.virtualcable.rdp.LinuxApplet;
import es.virtualcable.rdp.OsApplet;
import es.virtualcable.rdp.WindowsApplet;
import es.virtualcable.rdp.MacApplet;

public class RdpApplet extends Applet {
	/**
	 * 
	 */
	private static final long serialVersionUID = -7930346560654300533L;
	//private int width;
	//private int height;
	private OsApplet applet;
	private String appletStr = "UDS RDP Connector";

	public void init() {
		//width = getSize().width;
		//height = getSize().height;
		setBackground(Color.lightGray);
		
		try {
			AccessController.doPrivileged(new PrivilegedAction<Object>() {
				public Object run() {
					try {
						String os = System.getProperty("os.name");
						if( os.startsWith("Windows") )
							applet = new WindowsApplet();
						else if( os.startsWith("Linux"))
							applet = new LinuxApplet();
						else if (os.startsWith("Mac"))
							applet = new MacApplet();
						else
							throw new Exception("Invalid os!!!");
						
						Hashtable<String,String> params = parseParams(unscramble(getParameter("data")));
						String baseUrl = getCodeBase().toString();
						
						if( params.get("tun") != null )
							appletStr = "UDS RDP Tunnel Connector";
						
						Dimension scrSize = Toolkit.getDefaultToolkit().getScreenSize();
						
						applet.setParameters(params, baseUrl, scrSize.width, scrSize.height);
						applet.init();
						
						return null; // nothing to return
					} catch (Exception e) {
						e.printStackTrace();
						return null;
					}
				}
			});
		} catch (Exception e) {
			e.printStackTrace();
		}

	}
	
	public void start() {
		try {
			AccessController.doPrivileged(new PrivilegedAction<Object>() {
				public Object run() {
					try {
						applet.start();
						return null; // nothing to return
					} catch (Exception e) {
						e.printStackTrace();
						return null;
					}
				}
			});
		} catch (Exception e) {
			e.printStackTrace();
		}
	}
	
	public void destroy() {
		try {
			AccessController.doPrivileged(new PrivilegedAction<Object>() {
				public Object run() {
					try {
						applet.destroy();
						return null; // nothing to return
					} catch (Exception e) {
						e.printStackTrace();
						return null;
					}
				}
			});
		} catch (Exception e) {
			e.printStackTrace();
		}
	}
	
	public void paint(Graphics g) {
		g.setColor(Color.black);
		g.drawString(appletStr, 8, 16);
	}
	
	private Hashtable<String,String> parseParams(String params)
	{
		Hashtable<String,String> res = new Hashtable<String, String>();
		String[] parms = params.split("\t");
		for( int i = 0; i < parms.length;  i++) {
			String[] val = parms[i].split(":");
			if( val.length == 1 )
				res.put(val[0], "");
			else
				res.put(val[0], val[1]);
		}
		return res;
	}
	
	private String unscramble(String in)
	{
		int len = in.length();
		StringBuilder res = new StringBuilder(len/2);
		int val = 0x32;
		for( int i = 0; i < len; i += 2) {
			String b = in.substring(i, i+2);
			int c = Integer.parseInt(b, 16)^val;
			val = (val + c) & 0xFF;
			res.append((char)c);
		}
		  
		return res.reverse().toString();
	}
	
	
}
