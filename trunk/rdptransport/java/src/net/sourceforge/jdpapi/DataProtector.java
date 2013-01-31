package net.sourceforge.jdpapi;

/**
 * <p>An interface to the Microsoft Data Protection API (DPAPI).</p>
 * 
 * <p>See <a href="http://msdn2.microsoft.com/en-us/library/ms995355.aspx">MSDN</a> for more information</p>
 * 
 * @author <a href="mailto:kevin.a.conaway@gmail.com">Kevin Conaway</a>
 */
public class DataProtector {

    private final byte [] entropy;
    private final boolean localMachine;

    /**
     * @param entropy Additional entropy to include when encrypting (optional)
     * @param localMachine If true, allow all users on the machine to decrypt a given ciphertext
     * 
     */
    public DataProtector(byte[] entropy, boolean localMachine) {
        this.entropy = entropy;
        this.localMachine = localMachine;
    }

    /**
     * @param entropy
     * @see #DataProtector(byte[], boolean)
     */
    public DataProtector(byte[] entropy) {
        this(entropy, false);
    }

    /**
     * @param localMachine
     * @see #DataProtector(byte[], boolean)
     */
    public DataProtector(boolean localMachine) {
        this(null, localMachine);
    }

    /**
     * Initializes the protector with no additional entropy 
     * and {@code localMachine} set to false
     * @see #DataProtector(byte[], boolean)
     */
    public DataProtector() {
        this(false);
    }

    /**
     * <p>Protect {@code input} using the Microsoft DPAPI CryptProtectData function.</p>
     * 
     * <p>See the <a href="http://msdn2.microsoft.com/en-us/library/aa380261.aspx">CryptProtectData</a>
     * documentation for more details</p>
     * 
     * @param input Plaintext to encrypt
     * @return ciphertext
     */
    public byte[] protect(String input) {
        return DPAPI.CryptProtectData(input, entropy, localMachine);
    }

    /**
     * <p>Unprotect {@code input} using the Microsoft DPAPI CryptUnprotectData function.</p>
     * 
     * <p>See the <a href="http://msdn2.microsoft.com/en-us/library/aa380882.aspx">CryptUnprotectData</a>
     * documentation for more details</p>
     * 
     * @param input Ciphertext
     * @return Plaintext
     */
    public String unprotect(byte [] input) {
        return DPAPI.CryptUnprotectData(input, entropy);
    }
}