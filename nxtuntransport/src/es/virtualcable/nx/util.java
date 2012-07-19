package es.virtualcable.nx;

import java.io.BufferedInputStream;
import java.io.IOException;
import java.io.InputStream;

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
			System.out.println("Unable to download component, already present or network error? " + e.getMessage());
			return false;
		}
		return true;
	}
	
	
}
