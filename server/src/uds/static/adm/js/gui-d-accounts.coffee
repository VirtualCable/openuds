# jshint strict: true
gui.accounts = new GuiElement(api.accounts, "accounts")
gui.accounts.link = (event) ->
  "use strict"

  dateRenderer = gui.tools.renderDate(api.tools.djangoFormat(get_format("SHORT_DATETIME_FORMAT")))
  # Callback for custom fields
  renderer = (fld, data, type, record) ->
    # Display "custom" fields of rules table
    if fld == "time_mark"
      if data == 78793200
        return gettext('No Time Mark')
      return dateRenderer(data)
    return fld


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
      callback: renderer
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
        {
          text: gui.tools.iconAndText( 'fa-calendar', gettext('Set time mark') )
          css: "disabled"
          disabled: true
          click: (vals, value, btn, tbl, refreshFnc) ->
            val = vals[0]
            gui.forms.confirmModal gettext("Time Mark"), gettext("Set timemark to current datetime?"),
              onYes: ->
                gui.accounts.rest.timemark vals[0].id + "/timemark", ->
                  refreshFnc()
                  return

                return

            return

          select: (vals, value, btn, tbl, refreshFnc) ->
            unless vals.length == 1
              $(btn).addClass("disabled").prop('disabled', true)
              return

            $(btn).removeClass("disabled").prop('disabled', false)

        }
        "delete"
        "xls"
        "permissions"
      ]
      onNew: gui.methods.typedNew(gui.accounts, gettext("New Account"), gettext("Account creation error"))
      onEdit: gui.methods.typedEdit(gui.accounts, gettext("Edit Account"), gettext("Account saving error"))
      onDelete: gui.methods.del(gui.accounts, gettext("Delete Account"), gettext("Account deletion error"))
  false
false
