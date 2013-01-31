===================
UDS Modules Samples
===================

In this section we cover basic samples of the different kind of mudules supported
by UDS.

UDS is designed in a modular way, meaning this that it has a core that allows
a number of modules to get plugged inside the whole system.

This modules are:

   * Services, including all stuff around them.
   * Transports
   * OS Managers
   * Authenticators
   
This secion will try to give sample of every module, what it must do and how this
must be done.

Service Sample
--------------

A service is composed of several classes. This classes depends on how the service works. 

This are:

   * *Provider*, that is simply the "root" where services
     descent, so we can configure just one part of the service parameters and rest
     of them at service level.

     One sample of provider is a virtualization server, such as oVirt, Open Nebula, or
     others like it. We can keep info about server at provider level, and info about
     what we need in an specific service at service level.

   * *Service*, that is a service definition, that must be deployed at a later stage
     to offer something to the users.
     
     Following our previous sample, if provider was an oVirt server, a service can
     be a Virtual Machine cloned COW.
     
   * *Publication*, This class is optional. If service declares that needs a 
     publication for deployment of user instance, this class implements exactly
     that, the publication for that service. Publications are in fact a way of
     allowing services to prepare something in a stage prior to creating the
     user consumable services.
     
     Following our previous sample, if provider was an oVirt Server and the service
     was a Virtual Machine cloned for Cow, the poblication can be a full clone of 
     the service machine for making COWS from this one. 
     
   * *DeployedService*, This class is the user consumed service itself. After a
     service is created, it must be deployed, and deploy will mean that there will
     be "instances" of that service (User Deployments) that will be consumed by
     users. 
     
     Following our previous sample, if the publication was a full copy machine,
     an deployed service can be a machine in COW format using as base that
     machine.


From theese, the only not really needed is Publication. Publication will only be
needed whenever a service needs a "preparation" before creating the user consumable
deployed services. For a service to be usable, we will need the full tree, meaning
this that we will provide all controllers (Provider, service or services, publication
or publications, deployed service or deployed services.).

All class belonging to a service must be grouped under the same package, and we
well need to register this package for the system to recognize it as service.

For this, we must register the Provider, that has references to rest of items.

Provider declares which services it provides. Services declares which publication
and deployed service it needs. Provider can declare multiples services it offers,
but services has at most one publication and exatly one deployed service.

So, by registering the Provider, we register the whole tree provided by de package. 

Here you can find samples of every class needed for creating a new package of
services. 

.. toctree::

   services/whatisneeded
   services/Provider
   services/Service
   services/Publication
   services/DeployedServiceOne
   services/DeployedServiceTwo
   

Authenticator Sample
--------------------

An authenticator is composed of a single class, derived from :py:class:`uds.core.auths.Authenticator`.

Here you can find a sample of an authenticator.

.. toctree::
   auths/Authenticator