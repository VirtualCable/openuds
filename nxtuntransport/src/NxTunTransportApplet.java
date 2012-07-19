
import java.applet.*;
import java.awt.*;
import java.security.AccessController;
import java.security.PrivilegedAction;
import java.util.Hashtable;

import es.virtualcable.nx.LinuxApplet;
import es.virtualcable.nx.MacApplet;
import es.virtualcable.nx.OsApplet;
import es.virtualcable.nx.WindowsApplet;

public class NxTunTransportApplet extends Applet {
	/**
	 * 
	 */
	private static final long serialVersionUID = 6553108857320035827L;
	/**
	 * 
	 */
	//private int width;
	//private int height;
	private OsApplet applet;

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
						
						Hashtable<String,String> params = parseParams(simpleUnscrambler(getParameter("data")));
						String baseUrl = getCodeBase().toString();
						
						Dimension scrSize = Toolkit.getDefaultToolkit().getScreenSize();
						applet.setParameters(params, baseUrl, scrSize.width, scrSize.height);
						applet.init();
						
						return null; // nothing to return
					} catch (Exception e) {
						System.out.println("Exception:" + e.getMessage());
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
		g.drawString("UDS NX Tunel Connector", 8, 16);
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
	
	private String simpleUnscrambler(String in)
	{
		int len = in.length();
		StringBuilder res = new StringBuilder(len/2);
		int val = (int)'M';
		int pos = 0;
		for( int i = 0; i < len; i += 2, pos++) {
			String b = in.substring(i, i+2);
			int c = Integer.parseInt(b, 16)^val;
			val = (val ^ pos)&0xFF;
			res.append((char)c);
		}
		return res.toString();
	}
	
}
