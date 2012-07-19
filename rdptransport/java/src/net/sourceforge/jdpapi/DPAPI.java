package net.sourceforge.jdpapi;


class DPAPI {

    /**
     * See the <a href="http://msdn2.microsoft.com/en-us/library/aa380261.aspx">CryptProtectData</a>
     * documentation for more details
     * 
     * @param input Plaintext to encrypt
     * @param entropy Additional entropy to include when encrypting (optional)
     * @param localMachine If true, allow all users on the machine to decrypt the return ciphertext
     * @return ciphertext
     */
    static native byte [] CryptProtectData(String input, byte [] entropy, boolean localMachine);

    /**
     * See the <a href="http://msdn2.microsoft.com/en-us/library/aa380882.aspx">CryptUnprotectData</a>
     * documentation for more details
     * 
     * @param input Ciphertext
     * @param entropy Entropy that was included when {@code input} was encrypted
     * @return
     */
    static native String CryptUnprotectData(byte [] input, byte [] entropy);

}