========================
UserDeployment interface
========================

The user deployment class is in fact an interface. It represents the final consumable
that will be assigned to an user, and, as such, it must provide some mechanisms to
allow core to manage those consumables.

A good sample of an user deployment can be a KVM Virtual Machine, cloned COW from
another, and assigned to an user. 

.. toctree::

.. module:: uds.core.services

For detailed examples of a couple of user deployments, you can see the provided 
:doc:`service sample </development/samples/services/DeployedServiceOne>` and
:doc:`service sample </development/samples/services/DeployedServiceTwo>`

.. autoclass:: UserDeployment
   :members:

   
