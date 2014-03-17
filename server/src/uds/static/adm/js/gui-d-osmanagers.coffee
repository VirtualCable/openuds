#------------------------
# Os managers
#------------------------
gui.osmanagers = new GuiElement(api.osmanagers, "osm")
gui.osmanagers.link = (event) ->
  "use strict"
  api.templates.get "osmanagers", (tmpl) ->
    gui.clearWorkspace()
    gui.appendToWorkspace api.templates.evaluate(tmpl,
      osmanagers: "osmanagers-placeholder"
    )
    gui.osmanagers.table
      container: "osmanagers-placeholder"
      rowSelect: "single"
      buttons: [
        "new"
        "edit"
        "delete"
        "xls"
      ]
      onNew: gui.methods.typedNew(gui.osmanagers, gettext("New OSManager"), gettext("OSManager creation error"))
      onEdit: gui.methods.typedEdit(gui.osmanagers, gettext("Edit OSManager"), gettext("OSManager saving error"))
      onDelete: gui.methods.del(gui.osmanagers, gettext("Delete OSManager"), gettext("OSManager deletion error"))

    return

  return