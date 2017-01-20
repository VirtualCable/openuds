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
      icon: 'spool-group'
      container: "sPoolGroups-placeholder"
      rowSelect: "multi"
      buttons: [
        "new"
        "edit"
        "delete"
      ]
      onNew: gui.methods.typedNew(gui.sPoolGroups, gettext("New Services Pool Group"), gettext("Services Pool Group creation error"))
      onEdit: gui.methods.typedEdit(gui.sPoolGroups, gettext("Edit Services Pool Group"), gettext("Services Pool Group saving error"))
      onDelete: gui.methods.del(gui.sPoolGroups, gettext("Delete Services Pool Group"), gettext("Services Pool Group removal error"))
    return

  return
