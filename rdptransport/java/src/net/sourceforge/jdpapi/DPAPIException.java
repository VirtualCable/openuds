package net.sourceforge.jdpapi;

/**
 * Exception that can be thrown from the native DPAPI
 * 
 * @author <a href="mailto:kevin.a.conaway@gmail.com">Kevin Conaway</a>
 */
public class DPAPIException extends RuntimeException {

    private static final long serialVersionUID = 1l;

    public DPAPIException() {
        super();
    }

    public DPAPIException(String message, Throwable cause) {
        super(message, cause);
    }

    public DPAPIException(String message) {
        super(message);
    }

    public DPAPIException(Throwable cause) {
        super(cause);
    }

}