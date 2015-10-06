# jshint strict: true 
gui.providers = new GuiElement(api.providers, "provi")
gui.providers.link = (event) ->
  "use strict"
  
  # Button definition to trigger "Test" action
  testButton = testButton:
    text: gettext("Test")
    css: "btn-info"

  detailLogTable = undefined
  clearDetailLog = ->
    if detailLogTable
      $tbl = $(detailLogTable).dataTable()
      $tbl.fnClearTable()
      $tbl.fnDestroy()
      $("#services-log-placeholder").empty()
      detailLogTable = undefined
    return

  prevTables = []
  clearDetails = ->
    $.each prevTables, (undefined_, tbl) ->
      $tbl = $(tbl).dataTable()
      $tbl.fnClearTable()
      $tbl.fnDestroy()
      return

    clearDetailLog()
    prevTables = []
    $("#services-placeholder").empty()
    $("#logs-placeholder").empty()
    $("#detail-placeholder").addClass "hidden"
    return

  api.templates.get "providers", (tmpl) ->
    gui.clearWorkspace()
    gui.appendToWorkspace api.templates.evaluate(tmpl,
      providers: "providers-placeholder"
      provider_info: "provider-info-placeholder"
      services: "services-placeholder"
      services_log: "services-log-placeholder"
      logs: "logs-placeholder"
    )
    gui.setLinksEvents()
    
    # Append tabs click events
    $(".bottom_tabs").on "click", (event) ->
      setTimeout (->
        $($(event.target).attr("href") + " span.fa-refresh").click()
        return
      ), 10
      return

    tableId = gui.providers.table(
      icon: 'providers'
      container: "providers-placeholder"
      rowSelect: "multi"
      onCheck: (check, items) -> # Check if item can be deleted
        true

      onData: (data) ->
        $.each data, (index, value) ->
          if value.maintenance_mode is true
            value.maintenance_state = gettext('In Maintenance')
          else
            value.maintenance_state = gettext('Normal')

        return

      onRowDeselect: (deselected, dtable) ->
        if dtable.rows({selected: true}).count() != 1
          clearDetails()
        return

      onRowSelect: (selected) ->
        if selected.length > 1
          clearDetails()
          return

        gui.tools.blockUI()
        clearDetails()
        $("#detail-placeholder").removeClass "hidden"
        $('#detail-placeholder a[href="#provider-info-placeholder"]').tab('show')


        # Load provider "info"
        gui.methods.typedShow gui.providers, selected[0], '#provider-info-placeholder .well', gettext('Error accessing data')

        id = selected[0].id

        # Giving the name compossed with type, will ensure that only styles will be reattached once
        services = new GuiElement(api.providers.detail(id, "services", { permission: selected[0].permission }), "services-" + selected[0].type)
        tmpLogTable = undefined
        servicesTable = services.table(
          icon: 'services'
          container: "services-placeholder"
          doNotLoadData: true
          rowSelect: "multi"
          onRowSelect: (sselected) ->
            gui.tools.blockUI()
            sId = sselected[0].id
            clearDetailLog()
            tmpLogTable = services.logTable(sId,
              container: "services-log-placeholder"
              onLoad: ->
                detailLogTable = tmpLogTable
                gui.tools.unblockUI()
                return
            )
            return

          onRowDeselect: ->
            clearDetailLog()
            return

          onCheck: (check, items) ->
            if check is "delete" and items.length is 1
              return false  if items[0].deployed_services_count > 0
            return true
 
          buttons: [
            "new"
            "edit"
            "delete"
            "xls"
          ]
          onEdit: gui.methods.typedEdit(services, gettext("Edit service"), gettext("Service creation error"))
          onNew: gui.methods.typedNew(services, gettext("New service"), gettext("Service saving error"))
          onDelete: gui.methods.del(services, gettext("Delete service"), gettext("Service deletion error"),)
          scrollToTable: false
          onLoad: (k) ->
            gui.tools.unblockUI()
            return
        )
        logTable = gui.providers.logTable(id,
          container: "logs-placeholder"
          doNotLoadData: true
        )
        prevTables.push servicesTable
        prevTables.push logTable
        return

      buttons: [
        "new"
        "edit"
        {
          permission: api.permissions.MANAGEMENT
          text: gettext("Maintenance")
          css: "disabled"
          click: (vals, value, btn, tbl, refreshFnc) ->

            if vals.length > 1
              return

            val = vals[0]

            gui.promptModal gettext("Maintenance Mode"), (if val.maintenance_mode is false then gettext("Enter Maintenance Mode?") else gettext("Exit Maintenance Mode?")),
              onYes: ->
                gui.doLog 'Val: ', val
                api.providers.maintenance val.id, (->
                  refreshFnc()
                  ), (->)

                return

            return

            return

          select: (vals, value, btn, tbl, refreshFnc) ->
            unless vals.length == 1
              $(btn).removeClass("btn-warning").addClass "disabled"
              $(btn).empty().append(gettext("Maintenance"))
              return
            val = vals[0]
            $(btn).removeClass("disabled").addClass "btn-warning"
            $(btn).empty().append('<div>' + (if val.maintenance_mode is false then gettext('Enter maintenance Mode') else gettext('Exit Maintenance Mode')) + '</div>')
            return
        }
        "delete"
        "xls"
        "permissions"
      ]
      onNew: gui.methods.typedNew(gui.providers, gettext("New services provider"), gettext("Services provider creation error"), testButton)
      onEdit: gui.methods.typedEdit(gui.providers, gettext("Edit services provider"), gettext("Services Provider saving error"), testButton)
      onDelete: gui.methods.del(gui.providers, gettext("Delete services provider"), gettext("Services Provider deletion error"))
    )
    return

  false