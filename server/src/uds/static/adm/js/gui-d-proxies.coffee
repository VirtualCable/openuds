# jshint strict: true
gui.proxies = new GuiElement(api.proxies, "proxies")
gui.proxies.link = (event) ->
  "use strict"

  api.templates.get "proxies", (tmpl) ->
    gui.clearWorkspace()
    gui.appendToWorkspace api.templates.evaluate(tmpl,
      proxies: "proxies-placeholder"
    )
    gui.setLinksEvents()

    gui.proxies.table
      icon: 'proxy'
      container: "proxies-placeholder"
      rowSelect: "multiple"

      buttons: [
        "new"
        "edit"
        "delete"
        "xls"
        "permissions"
      ]
      onNew: gui.methods.typedNew(gui.proxies, gettext("New Proxy"), gettext("Account creation error"))
      onEdit: gui.methods.typedEdit(gui.proxies, gettext("Edit Proxy"), gettext("Account saving error"))
      onDelete: gui.methods.del(gui.proxies, gettext("Delete Proxy"), gettext("Account deletion error"))
  false
false
