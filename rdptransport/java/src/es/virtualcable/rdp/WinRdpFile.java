package es.virtualcable.rdp;

// More info about RDP files: http://technet.microsoft.com/en-us/library/ff393699%28WS.10%29.aspx

import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;
import net.sourceforge.jdpapi.DataProtector;

public class WinRdpFile {
	public String width;
	public String height;
	public boolean fullScreen;
	public String bpp;
	public String address = "";
	public String username = "";
	public String domain = "";
	public String password = "";
	public boolean redirectSerials = false;
	public boolean redirectPrinters = false;
	public boolean redirectDrives = false;
	public boolean redirectSmartcards = false;
	public boolean redirectAudio = false;
	public boolean compression = false;
	public boolean displayConnectionBar = true;
	public boolean showWallpaper = false;

	public WinRdpFile(boolean fullScreen, String width, String height, String bpp) {
		this.width = width;
		this.height = height;
		this.bpp = bpp;
		this.fullScreen = fullScreen;
	}

	public void saveFile(String fname) throws IOException {
		DataProtector d = new DataProtector(true);
		String pass = encode(d.protect(this.password));
		String screenMode = fullScreen ? "2" : "1";
		String audioMode = redirectAudio ? "0" : "2";
		String serials = redirectSerials ? "1" : "0";
		String drives = redirectDrives ? "1" : "0";
		String scards = redirectSmartcards ? "1" : "0";
		String printers = redirectPrinters ? "1" : "0";
		String compression = this.compression ? "1" : "0";
		String bar = displayConnectionBar ? "1" : "0";
		String disableWallpaper = showWallpaper ? "0" : "1";
		
		FileWriter fstream = new FileWriter(fname);
		PrintWriter out = new PrintWriter(fstream);
		out.println("screen mode id:i:" + screenMode);
		out.println("desktopwidth:i:"+this.width);
		out.println("desktopheight:i:"+this.height);
		out.println("session bpp:i:"+this.bpp);
		out.println("auto connect:i:1");
		out.println("full address:s:"+this.address);
		out.println("compression:i:"+compression);
		out.println("keyboardhook:i:2");
		out.println("audiomode:i:"+audioMode);
		out.println("redirectdrives:i:" + drives);
		out.println("redirectprinters:i:" + printers);
		out.println("redirectcomports:i:" + serials);
		out.println("redirectsmartcards:i:" + scards);
		out.println("redirectclipboard:i:1");
		out.println("displayconnectionbar:i:"+bar);
		if( this.username.length() != 0) {
			out.println("username:s:"+this.username);
			out.println("domain:s:"+this.domain);
			out.println("password 51:b:"+pass);
		}
		out.println("alternate shell:s:");
		out.println("shell working directory:s:");
		out.println("disable wallpaper:i:"+disableWallpaper);
		out.println("disable full window drag:i:1");
		out.println("disable menu anims:i:1");
		out.println("disable themes:i:1");
		out.println("bitmapcachepersistenable:i:1");
		out.println("authentication level:i:0");
		out.println("enablecredsspsupport:i:1");
		out.println("prompt for credentials:i:0");
		out.println("negotiate security layer:i:1");
		out.close();
	}

	protected static final byte[] Hexhars = {
			'0', '1', '2', '3', '4', '5', '6', '7', 
			'8', '9', 'a', 'b', 'c', 'd', 'e', 'f' };

	public static String encode(byte[] b) {

		StringBuilder s = new StringBuilder(2 * b.length);
		for (int i = 0; i < b.length; i++) {
			int v = b[i] & 0xff;
			s.append((char) Hexhars[v >> 4]);
			s.append((char) Hexhars[v & 0xf]);
		}

		return s.toString();
	}

}
