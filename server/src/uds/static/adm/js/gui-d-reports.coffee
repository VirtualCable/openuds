# jshint strict: true 
gui.reports = new GuiElement(api.reports, "reports")
gui.reports.link = (event) ->
  "use strict"

  api.templates.get "reports", (tmpl) ->
    gui.clearWorkspace()
    gui.appendToWorkspace api.templates.evaluate(tmpl,
      reports: "reports-placeholder"
    )
    gui.setLinksEvents()
    
    tableId = gui.reports.table(
      container: "reports-placeholder"
      rowSelect: "single"
      buttons: [
        {
          permission: api.permissions.MANAGEMENT
          text: gettext("Generate report")
          css: "disabled"
          click: (val, value, btn, tbl, refreshFnc) ->
            gui.doLog val.id
            api.reports.gui val.id, ((guiDefinition) ->
              gui.doLog 'aqui'
            )
            return

            return

          select: (val, value, btn, tbl, refreshFnc) ->
            unless val
              $(btn).removeClass("btn3d-primary").addClass "disabled"
              return
            $(btn).removeClass("disabled").addClass "btn3d-primary"
            return
        }
      ]
      onRowDeselect: ->
        return

      onRowSelect: (selected) ->
        return

      onRefresh: ->
        return
    )
    return

  false