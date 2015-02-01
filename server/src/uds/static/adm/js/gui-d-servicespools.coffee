# jshint strict: true 
gui.servicesPools = new GuiElement(api.servicesPools, "servicespools")
gui.servicesPools.link = (event) ->
  "use strict"
  gui.clearWorkspace()
  
  # Clears the details
  # Memory saver :-)
  prevTables = []
  clearDetails = ->
    $.each prevTables, (undefined_, tbl) ->
      $tbl = $(tbl).dataTable()
      $tbl.fnClearTable()
      $tbl.fnDestroy()
      return

    $("#assigned-services-placeholder_tbl").empty()
    $("#assigned-services-placeholder_log").empty()
    $("#cache-placeholder_tbl").empty()
    $("#cache-placeholder_log").empty()
    $("#transports-placeholder").empty()
    $("#groups-placeholder").empty()
    $("#logs-placeholder").empty()
    $("#detail-placeholder").addClass "hidden"
    prevTables = []
    return

  
  # On change base service
  preFnc = (formId) ->
    $fld = $(formId + " [name=\"service_id\"]")
    $osmFld = $(formId + " [name=\"osmanager_id\"]")
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
    $fld.on "change", (event) ->
      unless $fld.val() is -1
        api.providers.service $fld.val(), (data) ->
          gui.doLog "Onchange", data
          if data.info.needs_manager is false
            $osmFld.prop "disabled", "disabled"
          else
            $osmFld.prop "disabled", false
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

  # Fill "State" for cached and assigned services
  fillState = (data) ->
    states = {
      'R': gettext("Waiting for removal")
      'M': gettext("Removing")
      'S': gettext("Removed")
      'E': gettext("Error")
      'P': gettext("Generating")
      'K': gettext("Cancelling")
      'C': gettext("Cancelled")
    }
    $.each data, (index, value) ->
      value.origState = value.state  # Save original state for "cancel" checking
      if value.state is "U"
        value.state = if value.os_state isnt "" and value.os_state isnt "U" then gettext("Waiting OS") else value.state = gettext("Ready")
        return
      if states[value.state]?
        value.state = states[value.state]
        return
      value.state = gettext("Unknown")
      return

    return

  
  # Fills up the list of available services
  api.providers.allServices (services) ->
    availableServices = {}
    $.each services, (undefined_, service) ->
      availableServices[service.id] = service
      return

    gui.doLog "Available services", availableServices
    api.templates.get "services_pool", (tmpl) ->
      gui.appendToWorkspace api.templates.evaluate(tmpl,
        deployed_services: "deployed-services-placeholder"
        assigned_services: "assigned-services-placeholder"
        cache: "cache-placeholder"
        groups: "groups-placeholder"
        transports: "transports-placeholder"
        publications: "publications-placeholder"
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
        container: "deployed-services-placeholder"
        rowSelect: "single"
        buttons: [
          "new"
          "edit"
          "delete"
          "xls"
        ]
        onRowDeselect: ->
          clearDetails()
          return

        onRowSelect: (selected) ->
          servPool = selected[0]
          gui.doLog "Selected services pool", servPool
          clearDetails()
          service = null
          try
            service = availableServices[servPool.service_id]
          catch e
            gui.doLog "Exception on rowSelect", e
            gui.notify "Service pool " + gettext("error"), "danger"
            return
          if service?
            $("#detail-placeholder").removeClass "hidden"
          else
            $("#detail-placeholder").addClass "hidden"
            return
          
          # 
          #                     * Cache Part
          #                     
          cachedItems = null
          
          # If service does not supports cache, do not show it
          # Shows/hides cache
          if service.info.uses_cache or service.info.uses_cache_l2
            $("#cache-placeholder_tab").removeClass "hidden"
            cachedItems = new GuiElement(api.servicesPools.detail(servPool.id, "cache"), "cache")
            
            # Cached items table
            prevCacheLogTbl = null
            cachedItemsTable = cachedItems.table(
              container: "cache-placeholder_tbl"
              buttons: [
                "delete"
                "xls"
              ]
              rowSelect: "single"
              onData: (data) ->
                fillState data
                return

              onRowSelect: (selected) ->
                gui.do
                cached = selected[0]
                if prevCacheLogTbl
                  $tbl = $(prevCacheLogTbl).dataTable()
                  $tbl.fnClearTable()
                  $tbl.fnDestroy()
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
          if service.info.must_assign_manually is false
            $("#groups-placeholder_tab").removeClass "hidden"
            groups = new GuiElement(api.servicesPools.detail(servPool.id, "groups"), "groups")
            
            # Groups items table
            groupsTable = groups.table(
              container: "groups-placeholder"
              rowSelect: "single"
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
                        $.each data, (undefined_, value) ->
                          $select.append "<option value=\"" + value.id + "\">" + value.name + "</option>"
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

              onDelete: gui.methods.del(groups, gettext("Remove group"), gettext("Group removal error"))
              onData: (data) ->
                $.each data, (undefined_, value) ->
                  value.group_name = "<b>" + value.auth_name + "</b>\\" + value.name
                  return

                return
            )
            prevTables.push groupsTable
          else
            $("#groups-placeholder_tab").addClass "hidden"
          
          #
          #                     * Assigned services part
          #                     
          prevAssignedLogTbl = null
          assignedServices = new GuiElement(api.servicesPools.detail(servPool.id, "services"), "services")
          assignedServicesTable = assignedServices.table(
            container: "assigned-services-placeholder_tbl"
            rowSelect: "single"
            buttons: (if service.info.must_assign_manually then [
              "new"
              "delete"
              "xls"
            ] else [
              "delete"
              "xls"
            ])
            
            onData: (data) ->
              fillState data
              $.each data, (index, value) ->
                if value.in_use is true
                  value.in_use = gettext('Yes')
                else
                  value.in_use = gettext('No')

              return

            onRowSelect: (selected) ->
              service = selected[0]
              if prevAssignedLogTbl
                $tbl = $(prevAssignedLogTbl).dataTable()
                $tbl.fnClearTable()
                $tbl.fnDestroy()
              prevAssignedLogTbl = assignedServices.logTable(service.id,
                container: "assigned-services-placeholder_log"
              )
              return

            onDelete: gui.methods.del(assignedServices, gettext("Remove Assigned service"), gettext("Deletion error"))
          )
          
          # Log of assigned services (right under assigned services)
          prevTables.push assignedServicesTable
          
          #
          #                     * Transports part
          #                     
          transports = new GuiElement(api.servicesPools.detail(servPool.id, "transports"), "transports")
          
          # Transports items table
          transportsTable = transports.table(
            container: "transports-placeholder"
            rowSelect: "single"
            buttons: [
              "new"
              "delete"
              "xls"
            ]
            onNew: (value, table, refreshFnc) ->
              api.templates.get "pool_add_transport", (tmpl) ->
                api.transports.overview (data) ->
                  modalId = gui.launchModal(gettext("Add transport"), api.templates.evaluate(tmpl,
                    transports: data
                  ))
                  $(modalId + " .button-accept").on "click", (event) ->
                    transport = $(modalId + " #id_transport_select").val()
                    if transport is -1
                      gui.notify gettext("You must provide a transport"), "danger"
                    else # Save & close modal
                      transports.rest.create
                        id: transport
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

            onDelete: gui.methods.del(transports, gettext("Remove transport"), gettext("Transport removal error"))
            onData: (data) ->
              $.each data, (undefined_, value) ->
                style = "display:inline-block; background: url(data:image/png;base64," + value.type.icon + "); ; background-size: 16px 16px; background-repeat: no-repeat; width: 16px; height: 16px; vertical-align: middle;"
                value.trans_type = value.type.name
                value.name = "<span style=\"" + style + "\"></span> " + value.name
                return

              return
          )
          prevTables.push transportsTable
          
          #
          #                     * Publications part
          #                     
          publications = null
          if service.info.needs_publication
            $("#publications-placeholder_tab").removeClass "hidden"
            pubApi = api.servicesPools.detail(servPool.id, "publications")
            publications = new GuiElement(pubApi, "publications")
            
            # Publications table
            publicationsTable = publications.table(
              container: "publications-placeholder"
              rowSelect: "single"
              buttons: [
                "new"
                {
                  text: gettext("Cancel")
                  css: "disabled"
                  click: (val, value, btn, tbl, refreshFnc) ->
                    gui.promptModal gettext("Publish"), gettext("Cancel publication"),
                      onYes: ->
                        pubApi.invoke val.id + "/cancel", ->
                          refreshFnc()
                          return

                        return

                    return

                  select: (val, value, btn, tbl, refreshFnc) ->
                    unless val
                      $(btn).removeClass("btn3d-warning").addClass "disabled"
                      return

                    if val.state == 'K'
                      $(btn).empty().append(gettext("Force Cancel"))
                    else
                      $(btn).empty().append(gettext("Cancel"))

                    # Waiting for publication, Preparing or running
                    gui.doLog "State: ", val.state
                    $(btn).removeClass("disabled").addClass "btn3d-warning"  if [
                      "P"
                      "W"
                      "L"
                      "K"
                    ].indexOf(val.state) != -1

                    return
                }
                "xls"
              ]
              onNew: (action, tbl, refreshFnc) ->
                gui.promptModal gettext("Publish"), gettext("Launch new publication?"),
                  onYes: ->
                    pubApi.invoke "publish", (->
                      refreshFnc()
                      return
                    ), gui.failRequestModalFnc(gettext("Failed creating publication"))
                    return

                return
            )
            prevTables.push publicationsTable
          else
            $("#publications-placeholder_tab").addClass "hidden"
          
          #
          #                     * Log table
          #                     
          logTable = gui.servicesPools.logTable(servPool.id,
            container: "logs-placeholder"
          )
          prevTables.push logTable
          return

        
        # Pre-process data received to add "icon" to deployed service
        onData: (data) ->
          gui.doLog "onData", data
          $.each data, (index, value) ->
            gui.doLog value.thumb
            try
              service = availableServices[value.service_id]
              if not service?
                value.parent = gettext("undefined")
                return
              style = "display:inline-block; background: url(data:image/png;base64," + value.thumb + "); background-size: 16px 16px; background-repeat: no-repeat; width: 16px; height: 16px; vertical-align: middle;"
              gui.doLog style
              if value.restrained
                value.name = "<span class=\"fa fa-exclamation text-danger\"></span> " + value.name
                value.state = gettext("Restrained")
              value.name = "<span style=\"" + style + "\"></span> " + value.name
              value.parent = service.name
            catch e
              value.name = "<span class=\"fa fa-asterisk text-alert\"></span> " + value.name
              value.parent = gettext("unknown (needs reload)")
            return

          return

        onNew: gui.methods.typedNew(gui.servicesPools, gettext("New service pool"), "Service pool " + gettext("creation error"),
          guiProcessor: (guiDef) -> # Create has "save on publish" field
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
        onEdit: gui.methods.typedEdit(gui.servicesPools, gettext("Edit") + " service pool", "Service pool " + gettext("saving error"))
        onDelete: gui.methods.del(gui.servicesPools, gettext("Delete") + " service pool", "Service pool " + gettext("deletion error"))
      )
      return

    return

  return