# jshint strict: true 
gui.providers = new GuiElement(api.providers, "provi")
gui.providers.link = (event) ->
  "use strict"
  
  # Button definition to trigger "Test" action
  testButton = testButton:
    text: gettext("Test")
    css: "btn-info"

  detailLogTable = null
  clearDetailLog = ->
    if detailLogTable
      $tbl = $(detailLogTable).dataTable()
      $tbl.fnClearTable()
      $tbl.fnDestroy()
      $("#services-log-placeholder").empty()
      detailLogTable = `undefined`
    return

  prevTables = []
  clearDetails = ->
    gui.doLog "Clearing details"
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
      services: "services-placeholder"
      services_log: "services-log-placeholder"
      logs: "logs-placeholder"
    )
    gui.setLinksEvents()
    
    # Append tabs click events
    $(".bottom_tabs").on "click", (event) ->
      gui.doLog event.target
      setTimeout (->
        $($(event.target).attr("href") + " span.fa-refresh").click()
        return
      ), 10
      return

    tableId = gui.providers.table(
      container: "providers-placeholder"
      rowSelect: "single"
      onCheck: (check, items) -> # Check if item can be deleted
        #if( check == 'delete' ) {
        #                    for( var i in items ) {
        #                        if( items[i].services_count > 0)
        #                            return false;
        #                    }
        #                    return true;
        #                }
        true

      onRowDeselect: ->
        clearDetails()
        return

      onRowSelect: (selected) ->
        gui.tools.blockUI()
        clearDetails()
        $("#detail-placeholder").removeClass "hidden"
        id = selected[0].id
        
        # Giving the name compossed with type, will ensure that only styles will be reattached once
        services = new GuiElement(api.providers.detail(id, "services"), "services-" + selected[0].type)
        tmpLogTable = null
        servicesTable = services.table(
          container: "services-placeholder"
          rowSelect: "single"
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
            if check is "delete"
              for i of items
                return false  if items[i].deployed_services_count > 0
              return true
            true

          buttons: [
            "new"
            "edit"
            "delete"
            "xls"
          ]
          onEdit: gui.methods.typedEdit(services, gettext("Edit service"), gettext("Service creation error"), testButton)
          onNew: gui.methods.typedNew(services, gettext("New service"), gettext("Service saving error"), testButton)
          onDelete: gui.methods.del(services, gettext("Delete service"), gettext("Service deletion error"), testButton)
          scrollToTable: false
          onLoad: (k) ->
            gui.tools.unblockUI()
            return
        )
        logTable = gui.providers.logTable(id,
          container: "logs-placeholder"
        )
        prevTables.push servicesTable
        prevTables.push logTable
        return

      buttons: [
        "new"
        "edit"
        "delete"
        "xls"
      ]
      onNew: gui.methods.typedNew(gui.providers, gettext("New services provider"), gettext("Services provider creation error"), testButton)
      onEdit: gui.methods.typedEdit(gui.providers, gettext("Edit services provider"), gettext("Services Provider saving error"), testButton)
      onDelete: gui.methods.del(gui.providers, gettext("Delete services provider"), gettext("Services Provider deletion error"))
    )
    return

  false