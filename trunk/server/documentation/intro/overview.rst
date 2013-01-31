===============
UDS at a glance
===============

UDS has been developed to make a single open source server that allows the access
to the growing ip services catalog.

For this, we have try to make a framework that allows the use of any ip service,
focusing initially at VDI because it's the mayor need for the people we have
contacted initially  .

Also, first version of UDS has been developed "fast" (very fast indeed), so now
we need to make a revision an adapt de code of the framework so it's more
'pythonic'. (Think that i start learning python one day like this, and less than
a week later i started this proyect). So think that, althouth UDS is fully
functional, has been tested and is stable enought for any production environment,
there is a lot of work to do.

As so, UDS not only provides default modules for a lot of things (virtualization
provider, authentication providers, protocols, ...), but also provides the core
itself to allow anyone who wants or needs something, incorporate it to the 
catalog of UDS in an easy and fast way.

* In order to use UDS, you must simply :doc:`Follow the installation guide <install>`.

* In order to design and implement your own modules, you must:

   * :doc:`Understand the architecture </development/architecture>`
   * :doc:`See some module samples </development/samples/samples>`

* In order to contribute, you must install UDS, understand it, an read the 
  :doc:`contributing guide </development/contributing>` 