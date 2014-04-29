===============
Service Modules
===============

Service modules are responsible for giving the user consumable ip services for
users.

They are composed of a package where it is provided, at least, the following
elements:

   * One icon for administration interface representation. Icon is png file of 
     16x16.
   * A Full tree of classes, derived from interfaces (descrived below) 
   * Registration of the class inside UDS at package's __init__.
   
All packages included inside uds.services will automatically be imported, but
the service providers (root of service trees) needs to register as valid 
providers, and the best place to do that is at the authenticator's package __init__.

the Full tree of classes needed by the service modules are:

   * **Provider**: This is the root tree of any service. It represents an agrupation
     of services under the same root. As sample, a service provider can be an
     Open nebula server, an VC, or whataver is a common root for a number of services.
   * **Service**: This is the representation of what a service will give to an user.
     As such, this is not what the user will consume, but this is more the definition
     of what the user will consume. Before assigning a service to an user, the admin
     will need to declare a "Deployed Service", that is a definition, using this service
     an a number of other modules, of what the user will consume. Inside this service
     we need to provide the information needed for deploying an user consumable item, 
     such as if it needs to be "prepared", if it supports cache, if it must be assigned
     to an user "manually", and all the custom data that the user deployments and publications
     will need.
   * **Publication**. Some services, before being assigned to users, needs some kind of
     preparation. This process of preparation is called here "publication". The service
     itself will declare if it needs a publication and, if needed, who is responsible of
     that. Services with needed publication will use this kind of class to provide
     such preparation.
   * **User Deployment**. This is what will provide the final user consumable service.
     The user deployment is the last responsible for, using the provided service
     and provided publication (if needed), to create the elements that the user will
     consume.
      
The best way to understand what you need to create your own services,
is to look at :doc:`modules samples </development/samples/samples>`
     
.. toctree::

   services/Provider
   services/Service
   services/Publication
   services/UserDeployment
   services/Exceptions