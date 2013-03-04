package org.openuds.guacamole.creds;

import java.util.LinkedHashMap;

public class Credentials {

	private static CredentialsMap creds = new CredentialsMap();
	
	public static boolean put(String uuid, String credential, String value) {
		synchronized (creds) {
			if( uuid.equals(creds.uniqueId) ) { 
				creds.put(credential, value);
				return true;
			}
			return false;
		}
	}
	
	public static String get(String credential) {
		synchronized (creds) {
			return creds.get(credential);
		}
	}
	
	public static String getAndRemove(String credential) {
		synchronized (creds) {
			String cred = creds.get(credential);
			creds.put(credential, null);
			return cred;
			
		}
	}
	
	public static boolean test(String uuid) {
		synchronized (creds) {
			if( uuid.equals(creds.uniqueId) ) 
				return true;
			return false;
		}
		
	}
	
	
}

