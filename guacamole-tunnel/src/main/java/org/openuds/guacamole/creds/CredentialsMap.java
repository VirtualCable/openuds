package org.openuds.guacamole.creds;

import java.io.BufferedReader;
import java.io.DataInputStream;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.util.LinkedHashMap;

public class CredentialsMap extends LinkedHashMap<String, String> {
	
	private static final int MAX_CREDENTIALS = 1024;
	public String uniqueId;
	
	public CredentialsMap() {
		super(MAX_CREDENTIALS);
		try {
			FileInputStream fi = new FileInputStream("/etc/uniqueid.cfg");
			DataInputStream in = new DataInputStream(fi);
			BufferedReader br =  new BufferedReader(new InputStreamReader(in));
			uniqueId = br.readLine();
			in.close();
		} catch(Exception e) {
			uniqueId = null;
		}
	}
	
	@Override
	protected boolean removeEldestEntry(
			java.util.Map.Entry<String, String> eldest) {
		return size() >= MAX_CREDENTIALS;
	}
}
