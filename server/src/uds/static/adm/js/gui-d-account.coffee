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
        usage = new GuiElement(api.accounts.detail(id, "usage", { permission: selected[0].permission }), "Usage")
        usageTable = usage.table(
          icon: 'accounts'
          container: "usage-placeholder"
          rowSelect: "single"
          buttons: [
            "delete"
            "xls"
          ]
          onLoad: (k) ->
            # gui.tools.unblockUI()
            return # null return

          onData: (data) ->
            gui.doLog 'Accounts data received'
            $.each data, (index, value) ->
              value.running = if value.running then gettext('Yes') else gettext('No')
              return
            return

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
      onNew: gui.methods.typedNew(gui.accounts, gettext("New Account"), gettext("Account creation error"))
      onEdit: gui.methods.typedEdit(gui.accounts, gettext("Edit Account"), gettext("Account saving error"))
      onDelete: gui.methods.del(gui.accounts, gettext("Delete Account"), gettext("Account deletion error"))
  false
false
