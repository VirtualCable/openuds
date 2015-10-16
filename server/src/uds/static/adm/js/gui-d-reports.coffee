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
          click: (selecteds, value, btn, tbl, refreshFnc) ->
            if selecteds.length != 1
              return
            val = selecteds[0]
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
                actionButton: '<button type="button" class="btn btn-primary button-accept">'+ gettext('Generate report') + '</button>'
                success: (form_selector, closeFnc) ->
                  fields = gui.forms.read(form_selector)
                  gui.doLog fields
                  gui.tools.blockUI()
                  api.reports.save fields, ((data) -> # Success on put
                    gui.tools.unblockUI()
                    closeFnc()
                    gui.doLog data
                    if data.encoded
                      content = base64.decode(data.data)
                    else
                      content = data.data
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

            ), gui.failRequestModalFnc(gettext('Error obtaining report description'), true)
            return

            return

          select: (selecteds, clicked, btn, tbl, refreshFnc) ->
            gui.doLog "Selected", selecteds

            if selecteds.length is 0
              btn.addClass "disabled"
            else
              btn.removeClass("disabled")
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