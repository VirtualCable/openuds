gui.sPoolGroups = new GuiElement(api.sPoolGroups, "spal")
gui.sPoolGroups.link = ->
  gui.doLog 'Executing pool groups'
  "use strict"

  if api.config.admin is false
    return

  api.templates.get "services_pool_groups", (tmpl) ->
    gui.clearWorkspace()
    gui.appendToWorkspace api.templates.evaluate(tmpl,
      sPoolGroups: "sPoolGroups-placeholder"
    )
    gui.sPoolGroups.table
      icon: 'sPoolGroups'
      container: "sPoolGroups-placeholder"
      rowSelect: "single"
      buttons: [
        "new"
        "edit"
        "delete"
      ]
      onNew: gui.methods.typedNew(gui.sPoolGroups, gettext("New services Services Pool Group"), gettext("Services Services Pool Group creation error"))
      onEdit: gui.methods.typedEdit(gui.sPoolGroups, gettext("Edit services Services Pool Group"), gettext("Services Provider saving error"))
      onDelete: gui.methods.del(gui.sPoolGroups, gettext("Delete Services Pool Group"), gettext("Services Pool Group error"))
    return

  return