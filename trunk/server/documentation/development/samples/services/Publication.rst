==================
Sample publication
==================

A publication is a class responsible for making a service defined available to be
consumed by users.

Not all services needs publications as you have already seen if you are following
the samples. Publications are only needed for services that needs some kind of 
preparation, as, for example, with Virtual Machines, clone the base virtual machine
so we can create COW copies from this clone. This kind of behavior needs a preparation
step, that is efectively to clone the virtual base, and that will be the task of a
publication for that kind of services.

You can easily follow the code to see what it does, and what you have to do if you
want to provide a new one.

:download:`Download sample </_downloads/samples/services/SamplePublication.py>`


.. literalinclude:: /_downloads/samples/services/SamplePublication.py
   :linenos:

