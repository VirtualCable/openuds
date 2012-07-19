=====================
Publication interface
=====================

The publication class  is in fact an interface. It represents, in those case that
a service needs the preparation, the logic for that preparation.

So the publication class is responsible of doing whatever is needed to get the
deployed service (that is the compound of a service, an os manager, transports 
and authenticators) ready for deploying user consumables.

Note that not all services needs to implement this class, only in those case
where that service declares that a publication is needed.


As functional sample of a publication, imagine that we want to assing KVM COW
machines to users. The publication class can make a clone of the base machine
(that the service itself has taken note of which one is), and then the COWs will
be created from this cloned machine.

.. toctree::

.. module:: uds.core.services

For a detailed example of a service provider, you can see the provided 
:doc:`publication sample </development/samples/services/Publication>`

.. autoclass:: Publication
   :members:

