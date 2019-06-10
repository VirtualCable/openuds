==============
Installing UDS
==============

In order to run UDS, you will need:

   * Django Server 1.4
   * South module for Django
   * Mysql libraries for python
   * Mysql Database
   * Ldap Libraries for python
   * Criptographic package for python
   
Default transports are compiled in binary form, and kept inside the UDS repository,
so you won't need Java to put UDS to work.

Once you have all of this, you will have to follow these steps:

   * Obtain UDS from repository, you can see how to do this from
:doc:`repository access documentation </development/repository>`
   * Configure a database for use with UDS. To do this, simply create a database
     inside your Mysql server, and a user with all permissions in this database.
   * Configure UDS settings.
     Inside "server" folder, you will find "settings.py". This file contains the
     configuration of UDS (if it runs in debug mode, ..). The most important part
     here is the DATABASES section, where you will set up the database that UDS
     will use. Simply change "host", "port", "username", "password" and "name"
     to match your database settings.
     Here, we have to take care that, if we left UDS in debug mode, Django will keep
     track of all petitions to UDS, so memory will grow constantly. Do not get scared
     if you see that UDS starts consuming memory. Simply restart it or, if it's
     intended to be running for a while, set DEBUG variable to "False".
     Important sections are:
         
   * Create initial database tables.
     Inside UDS folder(where you downloaded it), you will see a "manage.py".
     This python application is the responsible for managing UDS, from database creation,
     migrations, backend start & stop, web server (testing web server btw), ...
     To create initial databases, we will do:
        
        python manage.py sync
        python manage.py migrate
     
     Now we have all databases and everything that UDS needs for starting up ready... :-)
     
 
