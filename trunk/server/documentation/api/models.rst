===================
UDS Database Models
===================

This section describes de models used in UDS.

The models described here are implemented using Django models, so you can get more
info about Django models functionalty at `Django project website <http://www.djangoproject.com/>`_

The function of the models inside UDS is to provide the persistence needed by
the core and by other utility classes that are provided, such as a Cache, Storage
or unique IDs.

Right now the models are used all over UDS, but with time we will limit the use
of this models to be done through managers or utility clases designed for that
purpose. 

.. toctree::

   models/services
   models/authentication
   models/transport
   models/other

