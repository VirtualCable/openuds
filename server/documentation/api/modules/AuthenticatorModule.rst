=====================
Authenticator Modules
=====================

Authenticator modules are responsible of providing the user authentication 
part inside UDS.

They are composed of a package where it is provided and, at least, the following
elements:

   * One icon for administration interface representation. Icon is png file of 
     16x16.
   * One class, derived from uds.core.auths.Authenticator, providing the needed
     logic for that authenticator.
   * Registration of the class inside uds at package's __init__.
   
All packages included inside uds.auths will automatically be imported, but
the authenticators needs to register as valid authenticators, and the best place
to do that is at the authenticator's package __init__.

The best way to understand what you need to create your own authenticator,
is to look at :doc:`modules samples </development/samples/samples>`


.. toctree::

   auths/Authenticator