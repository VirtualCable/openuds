package org.openuds.guacamole;

import java.util.Hashtable;
import org.openuds.guacamole.creds.Credentials;

public class Util {
	
	//
	public static Hashtable<String,String> readParameters(String data) {
		//String url = unscramble(data);
		//String params = getUrl(url);
		//return parseParams(params);
		String params = Credentials.getAndRemove(data);
		if( params == null )
			return null;
		return parseParams(params);
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
	
}