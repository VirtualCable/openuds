# jshint strict: true
gui.providers = new GuiElement(api.providers, "provi")

# To allow fast admin navigation
gui.providers.fastLink = (event, obj) ->
  gui.doLog 'FastLink clicked', obj
  event.preventDefault()
  event.stopPropagation()
  $obj = $(obj);
  if $obj.hasClass('goAuthLink')
    vals = $obj.attr('href').substr(1).split(',')
    gui.lookupUuid = vals[0]
    gui.lookup2Uuid = vals[1]
    setTimeout( ->
      $(".lnk-authenticators").click();
    , 50)
  else if $obj.hasClass('goPoolLink')
    gui.lookupUuid = $obj.attr('href').substr(1)
    setTimeout( ->
      $(".lnk-deployed_services").click();
    , 500);

gui.providers.link = (event) ->
  "use strict"

  # Button definition to trigger "Test" action
  testButton = testButton:
    text: gettext("Test")
    css: "btn-info"

  prevTables = []
  clearDetails = ->
    $.each prevTables, (undefined_, tbl) ->
      $tbl = $(tbl).dataTable()
      $tbl.fnClearTable()
      $tbl.fnDestroy()
      return

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
      usage: "usage-placeholder"
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

      onFoundUuid: (item) ->
        # Invoked if our table has found a "desirable" item (uuid)
        setTimeout( () ->
           $('a[href="#services-placeholder_tab"]').tab('show')
           $("#services-placeholder_tab span.fa-refresh").click()
        , 500)
        gui.lookupUuid = gui.lookup2Uuid
        gui.lookup2Uuid = null

      onRefresh: (tbl) ->
        clearDetails()
        return

      onData: (data) ->
        $.each data, (index, value) ->
          if value.maintenance_mode is true
            value.maintenance_state = gettext('In Maintenance')
          else
            value.maintenance_state = gettext('Active')

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
        servicesAPI = api.providers.detail(id, "services", { permission: selected[0].permission })
        services = new GuiElement(servicesAPI, "services-" + selected[0].type)
        tmpLogTable = undefined
        servicesTable = services.table(
          icon: 'services'
          container: "services-placeholder"
          doNotLoadData: true
          rowSelect: "multi"

          onCheck: (check, items) ->
            if check is "delete" and items.length is 1
              return false  if items[0].deployed_services_count > 0
            return true

          buttons: [
            "new"
            "edit"
            {
              text: gui.tools.iconAndText( 'fa-info', gettext('Information') )
              css: "disabled"
              disabled: true
              click: (vals, value, btn, tbl, refreshFnc) ->
                gui.doLog "Value:", value, vals[0]
                api.cache.clear()
                val = vals[0]
                servicesAPI.invoke val.id + "/servicesPools", (pools) ->
                  gui.doLog "Pools", pools
                  api.templates.get "service-info", (tmpl) ->
                    content = api.templates.evaluate(tmpl,
                      id: 'information',
                      pools: pools,
                      goClass: 'goLink'
                    )
                    modalId = gui.launchModal(gettext('Service information'), content,
                      actionButton: " "
                    )
                    gui.methods.typedShow services, val, '#information-overview', gettext('Error accessing data')
                    tmpLogTable = services.logTable(val.id,
                      container: "information-logs"
                      onLoad: ->
                        return
                    )
                    $('#information-pools-table').DataTable(
                      colReorder: true
                      stateSave: true
                      paging: true
                      info: true
                      autoWidth: false
                      lengthChange: false
                      pageLength: 10

                      columnDefs: [
                        { 'width': '50%', 'targets': 0 },
                        { 'width': '120px', 'targets': 1 },
                        { 'width': '40px', 'targets': 2 },
                        { 'width': '160px', 'targets': 3 },
                      ]

                      ordering: true
                      order: [[ 1, 'asc' ]]

                      dom: '<>fr<"uds-table"t>ip'

                      language: gui.config.dataTablesLanguage
                    )

                    $('.goLink').on('click', (event) ->
                      $this = $(this);
                      event.preventDefault();
                      gui.lookupUuid = $this.attr('href').substr(1)
                      $(modalId).modal('hide')
                      setTimeout( ->
                        $(".lnk-deployed_services").click();
                      , 500);
                    )

                  return

              select: (vals, value, btn, tbl, refreshFnc) ->
                unless vals.length == 1
                  $(btn).addClass("disabled").prop('disabled', true)
                  return

                $(btn).removeClass("disabled").prop('disabled', false)

            }
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

        usageAPI = api.providers.detail(id, "usage", { permission: selected[0].permission })
        usage = new GuiElement(usageAPI, "usage-" + selected[0].type)
        usageTable = usage.table(
          icon: 'usage'
          container: "usage-placeholder"
          doNotLoadData: true
          rowSelect: "multi"

          onData: (data) ->
            $.each data, (index, value) ->
              value.owner = gui.fastLink(value.owner.replace /@/, '<span class="text-danger">@</span>', "#{value.owner_info.auth_id},u#{value.owner_info.user_id}", 'gui.providers.fastLink', 'goAuthLink')
              value.pool = gui.fastLink(value.pool, value.pool_id, 'gui.providers.fastLink', 'goPoolLink')

          buttons: [
            "delete"
            "xls"
          ]
          onDelete: gui.methods.del(usage, gettext("Delete user service"), gettext("User service deletion error"),)
          scrollToTable: false
          onLoad: (k) ->
            gui.tools.unblockUI()
            return
        )
        prevTables.push usageTable

        return

      buttons: [
        "new"
        "edit"
        {
          permission: api.permissions.MANAGEMENT
          text: gui.tools.iconAndText('fa-ambulance', gettext("Maintenance"))
          css: "disabled"
          disabled: true
          click: (vals, value, btn, tbl, refreshFnc) ->

            if vals.length > 1
              return

            val = vals[0]

            gui.forms.confirmModal gettext("Maintenance Mode"), (if val.maintenance_mode is false then gettext("Enter Maintenance Mode?") else gettext("Exit Maintenance Mode?")),
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
              $(btn).removeClass("btn-warning").removeClass("btn-info").addClass("disabled").prop('disabled', true)
              $(btn).empty().append(gui.tools.iconAndText('fa-ambulance', gettext("Maintenance")))
              return
            val = vals[0]
            if val.maintenance_mode is false
              content = gui.tools.iconAndText('fa-ambulance', gettext('Enter maintenance Mode'))
              cls = 'btn-warning'
            else
              content = gui.tools.iconAndText('fa-truck',gettext('Exit Maintenance Mode'))
              cls = 'btn-info'

            $(btn).removeClass("disabled").addClass(cls).prop('disabled', false)
            $(btn).empty().append(content)
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
