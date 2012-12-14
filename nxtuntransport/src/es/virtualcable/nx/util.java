package es.virtualcable.nx;

import java.io.BufferedInputStream;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URLEncoder;

public class util {

	public static boolean download(String baseUrl, String id, String outputFileName)
	{
		try {
			java.net.URL u = new java.net.URL(baseUrl + id);
			java.net.URLConnection uc = u.openConnection();
		    String contentType = uc.getContentType();
		    int contentLength = uc.getContentLength();
		    if (contentType.startsWith("text/") || contentLength == -1) {
		      throw new IOException("This is not a binary file.");
		    }
		    InputStream raw = uc.getInputStream();
		    InputStream in = new BufferedInputStream(raw);
		    byte[] data = new byte[contentLength];
		    int bytesRead = 0;
		    int offset = 0;
		    while (offset < contentLength) {
		      bytesRead = in.read(data, offset, data.length - offset);
		      if (bytesRead == -1)
		        break;
		      offset += bytesRead;
		    }
		    in.close();

		    if (offset != contentLength) {
		      throw new IOException("Only read " + offset + " bytes; Expected " + contentLength + " bytes");
		    }		    
		    
			java.io.FileOutputStream out = new java.io.FileOutputStream(outputFileName);
		    out.write(data);
		    out.flush();
		    out.close();			
			
		} catch(Exception e) {
			System.out.println("Unable to download file, already present or network error? " + e.getMessage());
			return false;
		}
		return true;
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
	
	@SuppressWarnings("deprecation")
	public static void notifyHostname(String baseUrl, String serviceId) {
		String[] urlComponents = baseUrl.split("/");
		String hostname;
		String ip;
		String url="";
		
		try {
			hostname = java.net.InetAddress.getLocalHost().getHostName();
			ip = java.net.InetAddress.getLocalHost().getHostAddress();
		} catch(Exception e) {
			hostname = "unknown";
			ip = "0.0.0.0";
		}
		
		try {
			// An url is "http[s]://.....:/, 
			url = urlComponents[0] + "//" + urlComponents[2] + "/sernotify/" + serviceId + "/hostname?hostname="+URLEncoder.encode(hostname)+"&ip="+URLEncoder.encode(ip);
			getUrl(url);
		} catch(Exception e) {
			System.out.println("Unable to get url? " + e.getMessage());
		}
	}
	
}
