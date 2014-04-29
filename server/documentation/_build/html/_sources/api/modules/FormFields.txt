Form Fields
===========

Form Fields are utility clases provided for allowing easy communication of modules
and administration interface.

It helps to define the administration level forms that will be used to manage
different modules (service providers, services, authenticators, transports, ...)

All modules that needs to be presented to admin users, use UserInterface as one
of their base class.

Think that not all interfaces needed by different modules need a direct representation
at administration interface level, (for example, UserDeployment do not need to be
managed by administrators, nor publications, both corresponding to service modules).

.. module:: uds.core.ui.UserInterface

.. toctree::


The types of fields provided are:
   * :py:class:`gui.TextField`
   * :py:class:`gui.NumericField`
   * :py:class:`gui.PasswordField`
   * :py:class:`gui.HiddenField`
   * :py:class:`gui.CheckBoxField`
   * :py:class:`gui.ChoiceField`
   * :py:class:`gui.MultiChoiceField`
   * :py:class:`gui.EditableList`

.. autoclass:: gui
   :members: InputField, TextField, NumericField, PasswordField, HiddenField, CheckBoxField, ChoiceField, MultiChoiceField, EditableList
