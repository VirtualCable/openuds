==================
Provider interface
==================

The provider class is the root class of the module. It keeps the common information
needed by all services provided by this "provider".

Think about a provider as the class that will declare all stuff neded by core and
child services to provide and administrator user a way to create services to be
consumed by users. 

One good example is a Virtualization server. Here we keep information about that
server (ip address, protocol, ....) and services provided by that "provider" will
make use of that information to make the administrator not provide it once an again
for every service we put on that virtualization server.

.. toctree::

.. module:: uds.core.services

For a detailed example of a service provider, you can see the provided 
:doc:`provider sample </development/samples/services/Provider>`

.. autoclass:: ServiceProvider
   :members:

   
