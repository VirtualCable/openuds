# jshint strict: true
gui.accounts = new GuiElement(api.accounts, "accounts")
gui.accounts.link = (event) ->
  "use strict"

  useTable = undefined
  clearUsage = ->
    if useTable
      $tbl = $(useTable).dataTable()
      $tbl.fnClearTable()
      $tbl.fnDestroy()
      useTable = undefined
    $("#usage-placeholder").empty()
    $("#detail-placeholder").addClass "hidden"
    return

  api.templates.get "accounts", (tmpl) ->
    gui.clearWorkspace()
    gui.appendToWorkspace api.templates.evaluate(tmpl,
      accounts: "accounts-placeholder"
      usage: "usage-placeholder"
    )
    gui.setLinksEvents()

    gui.accounts.table
      icon: 'accounts'
      container: "accounts-placeholder"
      rowSelect: "single"

      onRefresh: (tbl) ->
        clearUsage()
        return

      onRowSelect: (selected) ->
        clearUsage()
        $("#detail-placeholder").removeClass "hidden"
        # gui.tools.blockUI()
        id = selected[0].id
        usage = new GuiElement(api.accounts.detail(id, "usage", { permission: selected[0].permission }), "rules")
        usageTable = usage.table(
          icon: 'calendars'
          container: "usage-placeholder"
          rowSelect: "single"
          buttons: [
            "new"
            "edit"
            "delete"
            "xls"
          ]
          onLoad: (k) ->
            # gui.tools.unblockUI()
            return # null return
        )
        return

      onRowDeselect: ->
        clearUsage()
        return
      buttons: [
        "new"
        "edit"
        "delete"
        "xls"
        "permissions"
      ]
      onNew: gui.methods.typedNew(gui.calendars, gettext("New calendar"), gettext("Calendar creation error"))
      onEdit: gui.methods.typedEdit(gui.calendars, gettext("Edit calendar"), gettext("Calendar saving error"))
      onDelete: gui.methods.del(gui.calendars, gettext("Delete calendar"), gettext("Calendar deletion error"))
  false
false
