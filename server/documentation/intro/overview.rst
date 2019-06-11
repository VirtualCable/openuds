===============
UDS at a glance
===============

UDS has been developed to make a single open source server that provides the access
to the growing ip services catalog.

For this, we have made a framework that allows the use of any ip service,
focusing initially at VDI because it's the major of people who have initially contacted us.

Also, first version of UDS has been developed "fast" (very fast indeed), so
we'll need to make a revision and adapt the code of the framework so it's more
'pythonic'. (Think that I start learning python one day, and less than
a week later I started this project). So althouth UDS is fully
functional and has been tested and is stable enough for any production environment,
there is a lot of work to do.

UDS not only provides default modules for a lot of things (virtualization
provider, authentication providers, protocols...), but also provides the core
itself to allow anyone who wants or needs something to incorporate it to the 
UDS catalog quickly and easily.

* In order to use UDS, you must simply :doc:`Follow the installation guide <install>`.

* In order to design and implement your own modules, you must:

   * :doc:`Understand the architecture </development/architecture>`
   * :doc:`See some module samples </development/samples/samples>`

* In order to contribute, you must install UDS, understand it, an read the 
  :doc:`contributing guide </development/contributing>` 
