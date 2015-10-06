#------------------------
# Os managers
#------------------------
gui.osmanagers = new GuiElement(api.osmanagers, "osm")
gui.osmanagers.link = (event) ->
  "use strict"
  clearDetails = ->
    $("#detail-placeholder").addClass "hidden"

  api.templates.get "osmanagers", (tmpl) ->
    gui.clearWorkspace()
    gui.appendToWorkspace api.templates.evaluate(tmpl,
      osmanagers: "osmanagers-placeholder"
      osmanager_info: "osmanagers-info-placeholder"
    )
    gui.osmanagers.table
      icon: 'osmanagers'
      container: "osmanagers-placeholder"
      rowSelect: "multi"

      onRowDeselect: (deselected, dtable) ->
        if dtable.rows({selected: true}).count() != 1
          clearDetails()
        return

      onRowSelect: (selected) ->
        if selected.length > 1
          clearDetails()
          return

        clearDetails()
        $("#detail-placeholder").removeClass "hidden"
        $('#detail-placeholder a[href="#osmanagers-info-placeholder"]').tab('show')

        # Load osmanager "info"
        gui.methods.typedShow gui.osmanagers, selected[0], '#osmanagers-info-placeholder .well', gettext('Error accessing data')

      buttons: [
        "new"
        "edit"
        "delete"
        "xls"
        "permissions"
      ]
      onNew: gui.methods.typedNew(gui.osmanagers, gettext("New OSManager"), gettext("OSManager creation error"))
      onEdit: gui.methods.typedEdit(gui.osmanagers, gettext("Edit OSManager"), gettext("OSManager saving error"))
      onDelete: gui.methods.del(gui.osmanagers, gettext("Delete OSManager"), gettext("OSManager deletion error"))

    return

  return