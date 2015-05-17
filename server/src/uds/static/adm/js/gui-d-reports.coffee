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
      icon: 'reports'
      container: "reports-placeholder"
      rowSelect: "single"
      buttons: [
        {
          permission: api.permissions.MANAGEMENT
          text: gettext("Generate report")
          css: "disabled"
          click: (val, value, btn, tbl, refreshFnc) ->
            gui.doLog val.id
            gui.tools.blockUI()
            # Get gui definition
            api.reports.gui val.id, ((guiDefinition) ->
              gui.tools.unblockUI()
              # Launch modal
              gui.forms.launchModal
                title: val.name
                fields: guiDefinition
                item:
                  id: val.id
                actionButton: '<button type="button" class="btn btn-primary button-accept" data-dismiss="modal">'+ gettext('Generate report') + '</button>'
                success: (form_selector, closeFnc) ->
                  fields = gui.forms.read(form_selector)
                  gui.doLog fields
                  api.reports.save fields, ((data) -> # Success on put
                    closeFnc()
                    gui.doLog data
                    content = base64.decode(data.data)
                    setTimeout( (()->
                        saveAs(
                          new Blob([content],
                                   type: data.content_type
                              ), 
                          data.filename
                        )
                      ), 100)
                    return
                  ), gui.failRequestModalFnc(gettext('Error creating report'), true)

            ), gui.failRequestModalFnc(gettext('Error obtainint report description'), true)
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