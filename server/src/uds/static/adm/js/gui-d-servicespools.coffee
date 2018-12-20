# jshint strict: true
gui.servicesPools = new GuiElement(api.servicesPools, "servicespools")

# To allow fast admin navigation
gui.servicesPools.fastLink = (event, obj) ->
  gui.doLog 'FastLink clicked', obj
  event.preventDefault()
  event.stopPropagation()
  $obj = $(obj);
  if $obj.hasClass('goServiceLink')
    vals = $obj.attr('href').substr(1).split(',')
    gui.lookupUuid = vals[0]
    gui.lookup2Uuid = vals[1]
    setTimeout( ->
      $(".lnk-service_providers").click();
    , 50
    )
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
  else if $obj.hasClass('goTransportLink')
    gui.lookupUuid = $obj.attr('href').substr(1)
    setTimeout( ->
      $(".lnk-connectivity").click();
    , 50)
  else if $obj.hasClass('goCalendarLink')
    gui.lookupUuid = $obj.attr('href').substr(1)
    setTimeout( ->
      $(".lnk-calendars").click();
    , 50)

gui.servicesPools.link = (event) ->
  "use strict"
  gui.clearWorkspace()
  editMode = false  # To indicate if editing or not. Used for disabling "os manager", due to the fact that os manager are different for apps and vdi

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

    $("#assigned-services-placeholder_tbl").empty()
    $("#assigned-services-placeholder_log").empty()
    $("#cache-placeholder_tbl").empty()
    $("#cache-placeholder_log").empty()
    $("#transports-placeholder").empty()
    $("#groups-placeholder").empty()
    $("#access-placeholder").empty()
    $("#scheduling-placeholder").empty()
    $("#logs-placeholder").empty()
    $("#detail-placeholder").addClass "hidden"
    prevTables = []
    return

  # Sets on change base service
  serviceChangedFnc = (formId) ->
    $fld = $(formId + " [name=\"service_id\"]")
    $osmFld = $(formId + " [name=\"osmanager_id\"]")
    $canResetFld = $(formId + " [name=\"allow_users_reset\"]")
    selectors = []
    $.each [
      "initial_srvs"
      "cache_l1_srvs"
      "cache_l2_srvs"
      "max_srvs"
    ], (index, value) ->
      selectors.push formId + " [name=\"" + value + "\"]"
      return

    $cacheFlds = $(selectors.join(","))
    $cacheL2Fld = $(formId + " [name=\"cache_l2_srvs\"]")
    $publishOnSaveFld = $(formId + " [name=\"publish_on_save\"]")

    unless $fld.val() is -1
      api.providers.service $fld.val(), (data) ->
        gui.doLog "Onchange", data
        if $canResetFld.bootstrapSwitch("readonly") == data.info.can_reset
          gui.doLog('reset doent not match field')
          $canResetFld.bootstrapSwitch "toggleReadonly", true
        if data.info.can_reset is false
          gui.doLog($canResetFld.bootstrapSwitch("readonly"), data.info.can_reset)
        
          
        if data.info.needs_manager is false
          $osmFld.prop "disabled", "disabled"
        else
          tmpVal = $osmFld.val()
          $osmFld.prop "disabled", false

          api.osmanagers.overview (osm) ->
            $osmFld.empty()
            for d in osm
              for st in d.servicesTypes
                if st in data.info.servicesTypeProvided
                  $osmFld.append('<option value="' + d.id + '">' + d.name + '</option>')
                  break
            $osmFld.val(tmpVal)
            if editMode is true
              $osmFld.prop "disabled", "disabled"
            $osmFld.selectpicker "refresh"  if $osmFld.hasClass("selectpicker")
            return

        if data.info.uses_cache is false
          $cacheFlds.prop "disabled", "disabled"
        else
          $cacheFlds.prop "disabled", false
          if data.info.uses_cache_l2 is false
            $cacheL2Fld.prop "disabled", "disabled"
          else
            $cacheL2Fld.prop "disabled", false
        gui.doLog "Needs publication?", data.info.needs_publication, $publishOnSaveFld
        # if switch y not as required..
        if $publishOnSaveFld.bootstrapSwitch("readonly") is data.info.needs_publication
          $publishOnSaveFld.bootstrapSwitch "toggleReadonly", true
        $osmFld.selectpicker "refresh"  if $osmFld.hasClass("selectpicker")
        return

      return

    return

  #
  preFnc = (formId) ->
    $fld = $(formId + " [name=\"service_id\"]")
    $fld.on "change", (event) ->
      serviceChangedFnc(formId)

  editDataLoaded = (formId) ->
    editMode = true
    serviceChangedFnc(formId)

  # Fill "State" for cached and assigned services
  fillState = (data) ->
    $.each data, (index, value) ->
      value.origState = value.state  # Save original state for "cancel" checking
      if value.state is "U"
        value.state = if value.os_state isnt "" and value.os_state isnt "U" then 'Z' else 'U'
      return
    return

  # Callback for custom fields
  renderer = (fld, data, type, record) ->
    # Display "custom" fields of rules table
    if fld == "show_transports" or fld == "visible"
      if data
        return gettext('Yes')
      return gettext('No')
    return fld

  api.templates.get "services_pool", (tmpl) ->
    gui.appendToWorkspace api.templates.evaluate(tmpl,
      deployed_services: "deployed-services-placeholder"
      pool_info: "pool-info-placeholder"
      assigned_services: "assigned-services-placeholder"
      cache: "cache-placeholder"
      groups: "groups-placeholder"
      transports: "transports-placeholder"
      publications: "publications-placeholder"
      changelog: "changelog-placeholder"
      actions: "actions-placeholder"
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
    #             * Services pools part
    #
    servicesPoolsTable = gui.servicesPools.table(
      icon: 'pools'
      callback: renderer
      container: "deployed-services-placeholder"
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

        servPool = selected[0]
        gui.doLog "Selected services pool", servPool
        clearDetails()
        service = null
        try
          info = servPool.info
        catch e
          gui.doLog "Exception on rowSelect", e
          gui.notify "Service pool " + gettext("error"), "danger"
          return

        $("#detail-placeholder").removeClass "hidden"
        $('#detail-placeholder a[href="#pool-info-placeholder"]').tab('show')

        # Load provider "info"
        gui.methods.typedShow gui.servicesPools, selected[0], '#pool-info-placeholder .well', gettext('Error accessing data')

        #
        #                     * Cache Part
        #
        cachedItems = null

        # If service does not supports cache, do not show it
        # Shows/hides cache
        if info.uses_cache or info.uses_cache_l2
          $("#cache-placeholder_tab").removeClass "hidden"

          cachedItems = new GuiElement(api.servicesPools.detail(servPool.id, "cache", { permission: servPool.permission }), "cache")

          # Cached items table
          prevCacheLogTbl = null

          clearCacheLog = (doHide) ->
            if prevCacheLogTbl
              $tbl = $(prevCacheLogTbl).dataTable()
              $tbl.fnClearTable()
              $tbl.fnDestroy()
              prevCacheLogTbl = null
              if doHide
                $('#cache-placeholder_log').empty()

          cachedItemsTable = cachedItems.table(
            icon: 'cached'
            container: "cache-placeholder_tbl"
            rowSelect: "multi"
            deferRender: true
            doNotLoadData: true
            buttons: [
              "delete"
              "xls"
            ]
            onData: (data) ->
              fillState data
              return

            onRefresh: () ->
              clearCacheLog(true)
              return

            onRowDeselect: (deselected, dtable) ->
              clearCacheLog(true)

            onRowSelect: (selected) ->
              cached = selected[0]
              clearCacheLog(false)
              prevCacheLogTbl = cachedItems.logTable(cached.id,
                container: "cache-placeholder_log"
              )
              return

            onDelete: gui.methods.del(cachedItems, gettext("Remove Cache element"), gettext("Deletion error"))
          )
          prevTables.push cachedItemsTable
        else
          $("#cache-placeholder_tab").addClass "hidden"

        #
        #                     * Groups part
        #
        groups = null

        # Shows/hides groups
        if info.must_assign_manually is false
          $("#groups-placeholder_tab").removeClass "hidden"
          groups = new GuiElement(api.servicesPools.detail(servPool.id, "groups", { permission: servPool.permission }), "groups")

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
                value.group_name = gui.fastLink("#{value.name}<span class='text-danger'>@</span>#{value.auth_name}", "#{value.auth_id},g#{value.id}", 'gui.servicesPools.fastLink', 'goAuthLink')
                return

              return

            onDelete: gui.methods.del(groups, gettext("Remove group"), gettext("Group removal error"))
          )
          prevTables.push groupsTable
        else
          $("#groups-placeholder_tab").addClass "hidden"

        #
        #                     * Assigned services part
        #
        prevAssignedLogTbl = null

        clearAssignedLog = (doHide) ->
            if prevAssignedLogTbl
              $tbl = $(prevAssignedLogTbl).dataTable()
              $tbl.fnClearTable()
              $tbl.fnDestroy()
              prevAssignedLogTbl = null
              if doHide
                $("#assigned-services-placeholder_log").empty()

        assignedServices = new GuiElement(api.servicesPools.detail(servPool.id, "services", { permission: servPool.permission }), "services")
        assignedServicesTable = assignedServices.table(
          doNotLoadData: true
          icon: 'assigned'
          container: "assigned-services-placeholder_tbl"
          rowSelect: "multi"
          buttons: (if info.must_assign_manually then [
            "new"
            "edit"
            "delete"
            "xls"
          ] else [
            "delete"
            "edit"
            "xls"
          ])

          onData: (data) ->
            fillState data
            $.each data, (index, value) ->
              if value.in_use is true
                value.in_use = gettext('Yes')
              else
                value.in_use = gettext('No')
              value.owner = gui.fastLink(value.owner.replace /@/, '<span class="text-danger">@</span>', "#{value.owner_info.auth_id},u#{value.owner_info.user_id}", 'gui.servicesPools.fastLink', 'goAuthLink')

            return

          onRefresh: () ->
            clearAssignedLog(true)
            return

          onRowDeselect: (deselected, dtable) ->
            clearAssignedLog(true)

          onRowSelect: (selected) ->
            svr = selected[0]
            clearAssignedLog(false)
            prevAssignedLogTbl = assignedServices.logTable(svr.id,
              container: "assigned-services-placeholder_log"
            )
            return

          onEdit: (item, event, table, refreshFnc) ->
            gui.doLog(item)
            if item.state in ['E', 'R', 'C']
              return
            api.templates.get "pool_edit_assigned", (tmpl) ->
              api.authenticators.overview (data) ->
                # Sorts groups, expression means that "if a > b returns 1, if b > a returns -1, else returns 0"
                api.authenticators.detail(item.owner_info.auth_id, "users").overview (users) ->
                  modalId = gui.launchModal(gettext("Edit Assigned Service ownership"), api.templates.evaluate(tmpl,
                    auths: data,
                    auth_id: item.owner_info.auth_id,
                    users: users,
                    user_id: item.owner_info.user_id,
                  ))
                  $(modalId + " #id_auth_select").on "change", (event) ->
                    auth = $(modalId + " #id_auth_select").val()
                    api.authenticators.detail(auth, "users").overview (data) ->
                      $select = $(modalId + " #id_user_select")
                      $select.empty()
                      $.each data, (undefined_, value) ->
                        console.log('Val: ', value)
                        $select.append "<option value=\"" + value.id + "\">" + value.name + "</option>"
                        return


                      # Refresh selectpicker if item is such
                      $select.selectpicker "refresh"  if $select.hasClass("selectpicker")
                      return

                    return

                  $(modalId + " .button-accept").on "click", (event) ->
                    auth = $(modalId + " #id_auth_select").val()
                    user = $(modalId + " #id_user_select").val()
                    if auth is -1 or user is -1
                      gui.notify gettext("You must provide authenticator and user"), "danger"
                    else # Save & close modal
                      assignedServices.rest.save
                        id: item.id,
                        auth_id: auth,
                        user_id: user
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

          onDelete: gui.methods.del(assignedServices, gettext("Remove Assigned service"), gettext("Deletion error"))
        )

        # Log of assigned services (right under assigned services)
        prevTables.push assignedServicesTable

        #
        #                     * Transports part
        #
        for v in gui.servicesPools.transports(servPool, info)
          prevTables.push v


        #
        #                     * Publications part
        #
        if info.needs_publication
          $("#publications-placeholder_tab").removeClass "hidden"
          for v in gui.servicesPools.publications(servPool, info)
            prevTables.push v
        else
          $("#publications-placeholder_tab").addClass "hidden"

        # Actions calendars
        for v in gui.servicesPools.actionsCalendars(servPool, info)
          prevTables.push v

        #
        # Access calendars
        #
        for v in gui.servicesPools.accessCalendars(servPool, info)
          prevTables.push v

        #
        #                     * Log table
        #
        logTable = gui.servicesPools.logTable(servPool.id,
          doNotLoadData: true
          container: "logs-placeholder"
        )
        prevTables.push logTable
        return

      # Pre-process data received to add "icon" to deployed service
      onData: (data) ->
        gui.doLog "onData for services pools", data
        $.each data, (index, value) ->
          try
            style = "display:inline-block; background: url(data:image/png;base64," + value.thumb + "); background-size: 16px 16px; background-repeat: no-repeat; width: 16px; height: 16px; vertical-align: middle;"
            style_grp = "display:inline-block; background: url(data:image/png;base64," + value.pool_group_thumb + "); background-size: 16px 16px; background-repeat: no-repeat; width: 16px; height: 16px; vertical-align: middle;"
            value.parent = gui.fastLink(value.parent, "#{value.provider_id},#{value.service_id}", 'gui.servicesPools.fastLink', 'goServiceLink')
            value.pool_group_name = "<span style='#{style_grp}'></span> #{value.pool_group_name}"
            if value.servicesPoolGroup_id?
               value.pool_group_name = gui.fastLink(value.pool_group_name, value.pool_group_id, 'gui.servicesPools.fastLink', 'goPoolGroupLink')
            if value.restrained
              value.name = "<span class=\"fa fa-exclamation text-danger\"></span> " + value.name
              value.state = gettext("Restrained")
            value.name = "<span style=\"" + style + "\"></span> " + value.name
          catch e
            value.name = "<span class=\"fa fa-asterisk text-alert\"></span> " + value.name
          return

        return

      onNew: gui.methods.typedNew(gui.servicesPools, gettext("New service pool"), "Service pool " + gettext("creation error"),
        guiProcessor: (guiDef) -> # Create has "publish on save" field
          editMode = false
          gui.doLog guiDef
          newDef = [].concat(guiDef).concat([
            name: "publish_on_save"
            value: true
            gui:
              label: gettext("Publish on creation")
              tooltip: gettext("If selected, will initiate the publication inmediatly after creation")
              type: "checkbox"
              order: 150
              defvalue: true
          ])
          gui.doLog newDef
          newDef

        preprocessor: preFnc
      )
      onEdit: gui.methods.typedEdit(gui.servicesPools, gettext("Edit") + " service pool", "Service pool " + gettext("saving error"), { preprocessor: editDataLoaded})
      onDelete: gui.methods.del(gui.servicesPools, gettext("Delete") + " service pool", "Service pool " + gettext("deletion error"))
    )
    return
  return
