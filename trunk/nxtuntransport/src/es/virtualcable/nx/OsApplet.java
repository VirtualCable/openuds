package es.virtualcable.nx;

import java.util.Hashtable;

public interface OsApplet {

	void setParameters(Hashtable<String,String> parameters, String urlBase, int screenWidth, int screenHeight);
	
	void init();
	
	void start();
	
	void destroy();
	
}
