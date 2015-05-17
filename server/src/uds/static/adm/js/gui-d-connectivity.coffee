# jshint strict: true 
gui.connectivity =
  transports: new GuiElement(api.transports, "trans")
  networks: new GuiElement(api.networks, "nets")

gui.connectivity.link = (event) ->
  "use strict"
  api.templates.get "connectivity", (tmpl) ->
    gui.clearWorkspace()
    gui.appendToWorkspace api.templates.evaluate(tmpl,
      transports: "transports-placeholder"
      networks: "networks-placeholder"
    )
    gui.connectivity.transports.table
      icon: 'transports'
      rowSelect: "single"
      container: "transports-placeholder"
      buttons: [
        "new"
        "edit"
        "delete"
        "xls"
        "permissions"
      ]
      onNew: gui.methods.typedNew(gui.connectivity.transports, gettext("New transport"), gettext("Transport creation error"))
      onEdit: gui.methods.typedEdit(gui.connectivity.transports, gettext("Edit transport"), gettext("Transport saving error"))
      onDelete: gui.methods.del(gui.connectivity.transports, gettext("Delete transport"), gettext("Transport deletion error"))

    gui.connectivity.networks.table
      icon: 'networks'
      rowSelect: "single"
      container: "networks-placeholder"
      buttons: [
        "new"
        "edit"
        "delete"
        "xls"
        "permissions"
      ]
      onNew: gui.methods.typedNew(gui.connectivity.networks, gettext("New network"), gettext("Network creation error"))
      onEdit: gui.methods.typedEdit(gui.connectivity.networks, gettext("Edit network"), gettext("Network saving error"))
      onDelete: gui.methods.del(gui.connectivity.networks, gettext("Delete network"), gettext("Network deletion error"))

    return

  return