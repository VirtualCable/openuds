package org.openuds.guacamole;

import java.io.IOException;

import javax.servlet.ServletException;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.PrintWriter;
import org.openuds.guacamole.creds.Credentials;

public class CredentialsServlet extends HttpServlet {
	
	/**
	 * 
	 */
	private static final long serialVersionUID = 8321644141165009209L;
	private static final String UUID_ERROR = "ERROR: Invalid UUID";
	private static final String PARAMS_ERROR = "ERROR: Invalid Credentials Parameters";
	private static final String OK = "OK";

	@Override
	protected void doGet(HttpServletRequest req, HttpServletResponse resp)
			throws ServletException, IOException {
		processCredentials(req, resp);
	}

	@Override
	protected void doPost(HttpServletRequest req, HttpServletResponse resp)
			throws ServletException, IOException {
		processCredentials(req, resp);
	}
	
	private void processCredentials(HttpServletRequest req, HttpServletResponse resp)
			throws ServletException, IOException {
		
		resp.setContentType("text/plain");
		PrintWriter out = resp.getWriter();
		
		String uuid = req.getParameter("uuid");
		String cred = req.getParameter("credential");
		String data = req.getParameter("data");
		
		if( req.getParameter("test") != null && uuid != null ) {
			if( Credentials.test(uuid) == false )
				out.println(UUID_ERROR);
			else
				out.println(OK);
			return;
		}
		
		if( uuid == null || cred == null || data == null ) {
			out.println(PARAMS_ERROR);
			return;
		}
		
		// Test url:
		// /creds?uuid=f070f721-15ea-44a9-8df1-b9480991989c&credential=12345&data=protocol%09rdp%0ahostname%09w7adolfo%0ausername%09admin%0apassword%09temporal
		
		if( Credentials.put(uuid, cred, data) == false )
			out.println(UUID_ERROR);
		else
			out.println(OK);
		
	}

}
