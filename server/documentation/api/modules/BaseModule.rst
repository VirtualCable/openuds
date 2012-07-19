===========
Base Module
===========

The Base module is the base class used for all modules of UDS.

In order to deveplop an UDS Module, there is a number of basic methods that you must provide.

There are the clases that are base of BaseModule, that are:
   * BaseModule_
   * Environmentable_
   * Serializable_
   * UserInterface_

.. toctree::

BaseModule
----------

.. module:: uds.core.BaseModule

.. autoclass:: BaseModule
   :members:
   
Environmentable
---------------

.. module:: uds.core.Environment

.. autoclass:: Environmentable
   :members:


Serializable
------------

.. module:: uds.core.Serializable

.. autoclass:: Serializable
   :members:


UserInterface
-------------

   UserInterface is the class responsible for managing the Field Descriptions of modules.
   
   This fields descriptions are intended for allowing an easy exposition of configuration form via the
   administration interface.
   
   You can obtain more information about user interface fields at :doc:`User interface fields types <FormFields>`.

.. module:: uds.core.ui.UserInterface

.. autoclass:: UserInterface
   :members: 

