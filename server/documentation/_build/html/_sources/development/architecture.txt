==================
UDS's architecture
==================

This section covers the current UDS Arquiceture & diagrams.

UDS is built on the Django web framework, which itself is
built on Python, thus MyTARDIS follows the architectural model
of Django.

Component Architecture
----------------------

This diagram shows the major components of UDS.

* Core components 
   * `Apache Http <http://projects.apache.org/projects/http_server.html>`_ 
   * `WSGI <http://code.google.com/p/modwsgi/>`_ 
   * `Django <http://www.djangoproject.com/>`_
   * `Python <http://docs.python.org/>`_.
   
* RDBMS
   UDS is currently being developed/testing on Mysql 5 Database.
   May other databases will work also, but no one else has been tested.
   
Functional Architecture
-----------------------

UDS is build using Django as base support for Web acess and Database access.

Over this, UDS uses the following diagram:

DIAGRAM

Core
   Basic core funcionality. 
