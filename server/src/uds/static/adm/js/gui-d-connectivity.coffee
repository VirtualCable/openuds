# jshint strict: true
gui.connectivity =
  transports: new GuiElement(api.transports, "trans")
  networks: new GuiElement(api.networks, "nets")

gui.connectivity.link = (event) ->
  "use strict"

  clearDetails = ->
    $("#detail-placeholder").addClass "hidden"

  api.templates.get "connectivity", (tmpl) ->
    gui.clearWorkspace()
    gui.appendToWorkspace api.templates.evaluate(tmpl,
      transports: "transports-placeholder"
      networks: "networks-placeholder"
      transport_info: 'transports-info-placeholder'
    )
    gui.connectivity.transports.table
      icon: 'transports'
      container: "transports-placeholder"
      rowSelect: "multi"

      onRefresh: (tbl) ->
        clearDetails()

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
        $('#detail-placeholder a[href="#transports-info-placeholder"]').tab('show')

        # Load osmanager "info"
        gui.methods.typedShow gui.connectivity.transports, selected[0], '#transports-info-placeholder .well', gettext('Error accessing data')

      onData: (data) ->
        $.each data, (undefined_, value) ->
          if value.allowed_oss != ''
            value.allowed_oss = (v.id for v in value.allowed_oss).toString()
          return

        return

      buttons: [
        "new"
        "edit"
        "delete"
        "xls"
        "permissions"
      ]
      onNew: gui.methods.typedNew(gui.connectivity.transports, gettext("New transport"), gettext("Transport creation error"))
      onEdit: gui.methods.typedEdit(gui.connectivity.transports, gettext("Edit transport"), gettext("Transport saving error"))
      onDelete: gui.methods.del(gui.connectivity.transports, gettext("Delete transport"), gettext("Transport deletion error"))

    gui.connectivity.networks.table
      icon: 'networks'
      rowSelect: "multi"
      container: "networks-placeholder"
      buttons: [
        "new"
        "edit"
        "delete"
        "xls"
        "permissions"
      ]
      onNew: gui.methods.typedNew(gui.connectivity.networks, gettext("New network"), gettext("Network creation error"))
      onEdit: gui.methods.typedEdit(gui.connectivity.networks, gettext("Edit network"), gettext("Network saving error"))
      onDelete: gui.methods.del(gui.connectivity.networks, gettext("Delete network"), gettext("Network deletion error"))

    return

  return
