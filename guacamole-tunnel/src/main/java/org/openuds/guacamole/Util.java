package org.openuds.guacamole;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.Hashtable;

public class Util {
	
	public static Hashtable<String,String> readParameters(String data) {
		//String url = unscramble(data);
		//String params = getUrl(url);
		//return parseParams(params);
		return parseParams("protocol\trdp\nhostname\tw7adolfo\nusername\tadmin\npassword\ttemporal");
	}
	
	public static Hashtable<String,String> parseParams(String params)
	{
		Hashtable<String,String> res = new Hashtable<String, String>();
		String[] parms = params.split("\n");
		for( int i = 0; i < parms.length;  i++) {
			String[] val = parms[i].split("\t");
			if( val.length == 1 )
				res.put(val[0], "");
			else
				res.put(val[0], val[1]);
		}
		return res;
	}
	
	public static String unscramble(String in)
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
	

	public static String getUrl(String url) {
		try {
			java.net.URL u = new java.net.URL(url);
			BufferedReader in = new BufferedReader(new InputStreamReader(u.openStream()));
			StringBuilder data = new StringBuilder();
			
			String inputLine;
			while ((inputLine = in.readLine()) != null) {
				data.append(inputLine);
				data.append("\n");
			}
				
			in.close();
			return data.toString();
			
		} catch(Exception e) {
			System.out.println("Unable to get url. Network error? " + e.getMessage());
			return null;
		}
		
	}
}