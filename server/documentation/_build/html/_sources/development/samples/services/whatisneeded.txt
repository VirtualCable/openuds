Needs for a service package
---------------------------

For a new package of services, you will need:


   * One package (python package), of course :-).   
   * One icon for the provider, in png format an 16x16 size. Colours is left
     to your election. This icon will be informed at Provider class.
   * One icon for every service that the provider will expose. Same as provider
     icons. These icons will be informed at Service class. Every single class
     must provide its own icon.
   * Registering the provider. For the samples show here, this will be at
     __init__ of the package.
     
     The contents of the sample package __init__ file is:

     .. literalinclude:: /_downloads/samples/services/__init__.py
        :linenos:

     :download:`Download sample </_downloads/samples/services/__init__.py>`

   * Put the package under the apropiate uds package. In the case of
     services, this is under "uds.core".
     
     Core will look for all packages under "uds.services" and import them at
     initialization of the server, so every package under this will get their 
     __init__ called, where we register the provider.

   * Follow the samples provided here as base

 