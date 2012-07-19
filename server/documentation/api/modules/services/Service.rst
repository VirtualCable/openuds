=================
Service interface
=================

The service class is in fact an interface. It represents the base for all user 
deployments (that is, consumable user services) that will be provided.

As such, the service is responsible for keeping the information that, at deployments,
will be neded by provided user consumable services.

A good sample of a service can be a KVM machine that will be copied COW and that COWs
will be assigned to users. In that case, we will collect which machine will be copied,
where it is to be copied, an a few more params that the user deployments will need.

.. toctree::

.. module:: uds.core.services

For a detailed example of a service provider, you can see the provided 
:doc:`service sample </development/samples/services/Service>`

.. autoclass:: Service
   :members:

   
