# jshint strict: true
gui.metaPools = new GuiElement(api.metaPools, "metapools")

# To allow fast admin navigation
gui.metaPools.fastLink = (event, obj) ->
  gui.doLog 'FastLink clicked', obj
  event.preventDefault()
  event.stopPropagation()
  $obj = $(obj);
  if $obj.hasClass('goPoolLink')
    gui.lookupUuid = $obj.attr('href').substr(1)
    setTimeout( ->
      $(".lnk-deployed_metapools").click();
    , 500);
  else if $obj.hasClass('goPoolGroupLink')
    gui.lookupUuid = $obj.attr('href').substr(1)
    setTimeout( ->
      $(".lnk-spoolsgroup").click();
    , 50
    )
  else if $obj.hasClass('goAuthLink')
    vals = $obj.attr('href').substr(1).split(',')
    gui.lookupUuid = vals[0]
    gui.lookup2Uuid = vals[1]
    setTimeout( ->
      $(".lnk-authenticators").click();
    , 50)
  else if $obj.hasClass('goCalendarLink')
    gui.lookupUuid = $obj.attr('href').substr(1)
    setTimeout( ->
      $(".lnk-calendars").click();
    , 50)

gui.metaPools.link = (event) ->
  "use strict"
  gui.clearWorkspace()

  # Clears the details
  # Memory saver :-)
  prevTables = []
  clearDetails = ->
    $.each prevTables, (undefined_, tbl) ->
      $(tbl).DataTable().destroy()
      #$tbl = $(tbl).dataTable()
      #$tbl.fnClearTable()
      #$tbl.fnDestroy()
      return

    $("#meta-service-pools-placeholder").empty()
    $("#groups-placeholder").empty()
    $("#access-placeholder").empty()
    $("#logs-placeholder").empty()
    $("#detail-placeholder").addClass "hidden"
    prevTables = []
    return


  #
  api.templates.get "meta_pools", (tmpl) ->
    gui.appendToWorkspace api.templates.evaluate(tmpl,
      meta_pools: "meta-pools-placeholder"
      meta_info: "meta-info-placeholder"
      meta_service_pools: "meta-service-pools-placeholder"
      groups: "groups-placeholder"
      access: "access-placeholder"
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


    #
    #             * metapools pools part
    #
    metaPoolsTable = gui.metaPools.table(
      icon: 'metas'
      container: "meta-pools-placeholder"
      rowSelect: "multi"
      buttons: [
        "new"
        "edit"
        "delete"
        "xls"
        "permissions"
      ]
      onRefresh: () ->
        clearDetails()
        return

      onRowDeselect: (deselected, dtable) ->
        gui.doLog "Selecteds: ", dtable.rows({selected: true}).length
        if dtable.rows({selected: true}).count() == 0
          clearDetails()
        return

      onRowSelect: (selected) ->
        if selected.length > 1
          clearDetails()
          return

        metaPool = selected[0]
        gui.doLog "Selected metapools pool", metaPool
        clearDetails()
        service = null
        try
          info = metaPool.info
        catch e
          gui.doLog "Exception on rowSelect", e
          gui.notify "Service pool " + gettext("error"), "danger"
          return

        $("#detail-placeholder").removeClass "hidden"
        $('#detail-placeholder a[href="#meta-info-placeholder"]').tab('show')

        # Load provider "info"
        gui.methods.typedShow gui.metaPools, selected[0], '#meta-info-placeholder .well', gettext('Error accessing data')

        #
        #                     * Services pools part
        #
        servicePool = new GuiElement(api.metaPools.detail(metaPool.id, "pools", { permission: metaPool.permission }), "pools")

        # servicePool items table
        servicePoolTable = servicePool.table(
          doNotLoadData: true
          icon: 'pool'
          container: "meta-service-pools-placeholder"
          rowSelect: "multi"
          buttons: [
            "new"
            "edit"
            "delete"
            "xls"
          ]
        )
        prevTables.push servicePoolTable

        #
        #                     * Groups part
        #

        # Shows/hides groups
        groups = new GuiElement(api.metaPools.detail(metaPool.id, "groups", { permission: metaPool.permission }), "groups")

        # Groups items table
        groupsTable = groups.table(
          doNotLoadData: true
          icon: 'groups'
          container: "groups-placeholder"
          rowSelect: "multi"
          buttons: [
            "new"
            "delete"
            "xls"
          ]
          onNew: (value, table, refreshFnc) ->
            api.templates.get "pool_add_group", (tmpl) ->
              api.authenticators.overview (data) ->
                # Sorts groups, expression means that "if a > b returns 1, if b > a returns -1, else returns 0"

                modalId = gui.launchModal(gettext("Add group"), api.templates.evaluate(tmpl,
                  auths: data
                ))
                $(modalId + " #id_auth_select").on "change", (event) ->
                  auth = $(modalId + " #id_auth_select").val()
                  api.authenticators.detail(auth, "groups").overview (data) ->
                    $select = $(modalId + " #id_group_select")
                    $select.empty()
                    # Sorts groups, expression means that "if a > b returns 1, if b > a returns -1, else returns 0"
                    maxCL = 32
                    $.each data, (undefined_, value) ->
                      $select.append "<option value=\"" + value.id + "\">" + value.name + " (" + value.comments.substr(0, maxCL - 1) + ((if value.comments.length > maxCL then "&hellip;" else "")) + ")</option>"
                      return


                    # Refresh selectpicker if item is such
                    $select.selectpicker "refresh"  if $select.hasClass("selectpicker")
                    return

                  return

                $(modalId + " .button-accept").on "click", (event) ->
                  auth = $(modalId + " #id_auth_select").val()
                  group = $(modalId + " #id_group_select").val()
                  if auth is -1 or group is -1
                    gui.notify gettext("You must provide authenticator and group"), "danger"
                  else # Save & close modal
                    groups.rest.create
                      id: group
                    , (data) ->
                      $(modalId).modal "hide"
                      refreshFnc()
                      return

                  return


                # Makes form "beautyfull" :-)
                gui.tools.applyCustoms modalId
                return

              return

            return

          onData: (data) ->
            $.each data, (undefined_, value) ->
              value.group_name = gui.fastLink("#{value.name}<span class='text-danger'>@</span>#{value.auth_name}", "#{value.auth_id},g#{value.id}", 'gui.metaPools.fastLink', 'goAuthLink')
              return

            return

          onDelete: gui.methods.del(groups, gettext("Remove group"), gettext("Group removal error"))
        )
        prevTables.push groupsTable

        #
        # Access calendars
        #
        for v in gui.metaPools.accessCalendars(metaPool, info)
          prevTables.push v

        #
        #                     * Log table
        #
        logTable = gui.metaPools.logTable(metaPool.id,
          doNotLoadData: true
          container: "logs-placeholder"
        )
        prevTables.push logTable
        return

      # Pre-process data received to add "icon" to deployed service
      onData: (data) ->
        gui.doLog "onData for metapools pools", data
        $.each data, (index, value) ->
          try
            style = "display:inline-block; background: url(data:image/png;base64," + value.thumb + "); background-size: 16px 16px; background-repeat: no-repeat; width: 16px; height: 16px; vertical-align: middle;"
            style_grp = "display:inline-block; background: url(data:image/png;base64," + value.pool_group_thumb + "); background-size: 16px 16px; background-repeat: no-repeat; width: 16px; height: 16px; vertical-align: middle;"
            value.parent = gui.fastLink(value.parent, "#{value.provider_id},#{value.service_id}", 'gui.metaPools.fastLink', 'goServiceLink')
            value.pool_group_name = "<span style='#{style_grp}'></span> #{value.pool_group_name}"
            if value.metapoolsPoolGroup_id?
               value.pool_group_name = gui.fastLink(value.pool_group_name, value.pool_group_id, 'gui.metaPools.fastLink', 'goPoolGroupLink')
            if value.restrained
              value.name = "<span class=\"fa fa-exclamation text-danger\"></span> " + value.name
              value.state = gettext("Restrained")
            value.name = "<span style=\"" + style + "\"></span> " + value.name
          catch e
            value.name = "<span class=\"fa fa-asterisk text-alert\"></span> " + value.name
          return

        return

      onNew: gui.methods.typedNew(gui.metaPools, gettext("New meta pool"), "Meta pool " + gettext("creation error"))
      onEdit: gui.methods.typedEdit(gui.metaPools, gettext("Edit") + " service pool", "Service pool " + gettext("saving error"))
      onDelete: gui.methods.del(gui.metaPools, gettext("Delete") + " service pool", "Service pool " + gettext("deletion error"))
    )
    return
  return
