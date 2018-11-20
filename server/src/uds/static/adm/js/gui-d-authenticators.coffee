# jshint strict: true
gui.authenticators = new GuiElement(api.authenticators, "auth")
gui.authenticators.link = (event) ->
  "use strict"

  # Button definition to trigger "Test" action
  testButton = testButton:
    text: gettext("Test")
    css: "btn-info"


  # Clears the log of the detail, in this case, the log of "users"
  # Memory saver :-)
  detailLogTable = null
  clearDetailLog = ->
    if detailLogTable?
      $tbl = $(detailLogTable).dataTable()
      $tbl.fnClearTable()
      $tbl.fnDestroy()
      detailLogTable = null
    $("#users-log-placeholder").empty()
    return


  # Clears the details
  # Memory saver :-)
  prevTables = []
  clearDetails = ->
    clearDetailLog()

    $.each prevTables, (undefined_, tbl) ->
      $tbl = $(tbl).dataTable()
      $tbl.fnClearTable()
      $tbl.fnDestroy()
      return

    $("#users-placeholder").empty()
    $("#groups-placeholder").empty()
    $("#logs-placeholder").empty()
    $("#detail-placeholder").addClass "hidden"
    prevTables = []
    return


  # Search button event generator for user/group
  searchForm = (parentModalId, type, id, title, searchLabel, resultsLabel) ->
    errorModal = gui.failRequestModalFnc(gettext("Search error"))
    srcSelector = parentModalId + " input[name=\"name\"]"
    $(parentModalId + " .button-search").on "click", ->
      api.templates.get "search", (tmpl) -> # Get form template
        modalId = gui.launchModal(title, api.templates.evaluate(tmpl,
          search_label: searchLabel
          results_label: resultsLabel
        ),
          actionButton: "<button type=\"button\" class=\"btn btn-success button-accept\">" + gettext("Accept") + "</button>"
        )
        $searchInput = $(modalId + " input[name=\"search\"]")
        $select = $(modalId + " select[name=\"results\"]")
        $searchButton = $(modalId + " .button-do-search")
        $saveButton = $(modalId + " .button-accept")
        $searchInput.val $(srcSelector).val()
        $saveButton.on "click", ->
          value = $select.val()
          if value
            $(srcSelector).val value
            $(modalId).modal "hide"
          return

        $searchButton.on "click", ->
          $searchButton.addClass "disabled"
          term = $searchInput.val()
          api.authenticators.search id, type, term, ((data) ->
            $searchButton.removeClass "disabled"
            $select.empty()
            gui.doLog data
            $.each data, (undefined_, value) ->
              $select.append($('<option>',
                value: value.id
                text: value.id + "   (" + value.name + ")"
              ))
              return

            return
          ), (jqXHR, textStatus, errorThrown) ->
            $searchButton.removeClass "disabled"
            errorModal jqXHR, textStatus, errorThrown
            return

          return

        $(modalId + " form").submit (event) ->
          event.preventDefault()
          $searchButton.click()
          return

        $searchButton.click()  if $searchInput.val() isnt ""
        return

      return

    return

  api.templates.get "authenticators", (tmpl) ->
    gui.clearWorkspace()
    gui.appendToWorkspace api.templates.evaluate(tmpl,
      auths: "auths-placeholder"
      auths_info: "auths-info-placeholder"
      users: "users-placeholder"
      users_log: "users-log-placeholder"
      groups: "groups-placeholder"
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

    tableId = gui.authenticators.table(
      icon: 'authenticators'
      container: "auths-placeholder"
      rowSelect: "multi"
      buttons: [
        "new"
        "edit"
        "delete"
        "xls"
        "permissions"
      ]

      onFoundUuid: (item) ->
        # Invoked if our table has found a "desirable" item (uuid)
        if gui.lookup2Uuid?
          type = gui.lookup2Uuid[0]
          gui.lookupUuid = gui.lookup2Uuid.substr(1)
          gui.lookup2Uuid = null
          setTimeout( () ->
            if type == 'g'
              $('a[href="#groups-placeholder"]').tab('show')
              $("#groups-placeholder span.fa-refresh").click()
            else
              $('a[href="#users-placeholder_tab"]').tab('show')
              $("#users-placeholder_tab span.fa-refresh").click()
          , 500)

      onRefresh: (tbl) ->
        gui.doLog 'Refresh called for authenticators'
        clearDetails()
        return

      onRowDeselect: (deselected, dtable) ->
        clearDetails()
        return

      onRowSelect: (selected) ->
        clearDetails()

        if selected.length > 1
          return

        # We can have lots of users, so memory can grow up rapidly if we do not keep thins clean
        # To do so, we empty previous table contents before storing new table contents
        # Anyway, TabletTools will keep "leaking" memory, but we can handle a little "leak" that will be fixed as soon as we change the section
        $("#detail-placeholder").removeClass "hidden"
        $('#detail-placeholder a[href="#auths-info-placeholder"]').tab('show')

        gui.tools.blockUI()

        # Load provider "info"
        gui.methods.typedShow gui.authenticators, selected[0], '#auths-info-placeholder .well', gettext('Error accessing data')

        id = selected[0].id
        type = gui.authenticators.types[selected[0].type]
        gui.doLog "Type", type
        user = new GuiElement(api.authenticators.detail(id, "users", { permission: selected[0].permission }), "users")
        group = new GuiElement(api.authenticators.detail(id, "groups", { permission: selected[0].permission }), "groups")
        grpTable = group.table(
          icon: 'groups'
          container: "groups-placeholder"
          doNotLoadData: true
          rowSelect: "multi"
          buttons: [
            "new"
            "edit"
            {
              text: gui.tools.iconAndText( 'fa-info', gettext('Information') )
              css: "disabled"
              disabled: true

              click: (vals, value, btn, tbl, refreshFnc) ->

                if vals.length > 1
                  return

                val = vals[0]
                group.rest.invoke val.id + "/servicesPools", (pools) ->
                  group.rest.invoke val.id + "/users", (users) ->
                    group.rest.overview (groups) -> # Get groups
                      renderDate = gui.tools.renderDate(api.tools.djangoFormat(get_format("SHORT_DATETIME_FORMAT")))
                      #for _, i in users
                      #  users[i].last_access = renderDate(users[i].last_access)

                      gui.tools.renderDate(api.tools.djangoFormat(get_format("SHORT_DATETIME_FORMAT")))
                      gui.doLog "Pools", pools
                      api.templates.get "group-info", (tmpl) ->
                        content = api.templates.evaluate(tmpl,
                          id: 'information',
                          pools: pools,
                          users: users,
                          groups: if val.type == 'meta' then val.groups else null,
                          meta: val.type == 'meta',
                          meta_if_any: val.meta_if_any,
                          groups_all: groups,
                          goClass: 'goLink'
                        )
                        modalId = gui.launchModal(gettext('Group information'), content,
                          actionButton: " "
                        )

                        $('#information-pools-table').DataTable(
                          colReorder: true
                          stateSave: true
                          paging: true
                          info: false
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

                        $('#information-users-table').DataTable(
                          colReorder: true
                          stateSave: true
                          paging: true
                          info: false
                          autoWidth: false
                          lengthChange: false
                          pageLength: 10

                          columnDefs: [
                            { 'width': '30%', 'targets': 0 },
                            { 'width': '30%', 'targets': 1 },
                            { 'width': '15%', 'targets': 2 },
                            { 'width': '25%', 'targets': 3, 'render': renderDate },
                          ]

                          ordering: true
                          order: [[ 1, 'asc' ]]

                          dom: '<>fr<"uds-table"t>ip'

                          language: gui.config.dataTablesLanguage
                        )

                        $('#information-groups-table').DataTable(
                          colReorder: true
                          stateSave: true
                          paging: true
                          info: false
                          autoWidth: false
                          lengthChange: false
                          pageLength: 10

                          columnDefs: [
                            { 'width': '40%', 'targets': 0 },
                            { 'width': '60%', 'targets': 1 },
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
                return

            }
            "delete"
            "xls"
          ]
          onLoad: (k) ->
            gui.tools.unblockUI()
            return

          onEdit: (value, event, table, refreshFnc) ->
            exec = (groups_all) ->
              api.servicesPools.summary (servicePools) ->
                gui.tools.blockUI()
                api.templates.get "group", (tmpl) -> # Get form template
                  group.rest.item value.id, (item) -> # Get item to edit
                    if item.type is 'meta'
                      servicePools = undefined
                    # Creates modal
                    modalId = gui.launchModal(gettext("Edit group") + " <b>" + item.name + "</b>", api.templates.evaluate(tmpl,
                      id: item.id
                      type: item.type
                      meta_if_any: item.meta_if_any
                      groupname: item.name
                      groupname_label: type.groupNameLabel
                      comments: item.comments
                      state: item.state
                      external: type.isExternal
                      canSearchGroups: type.canSearchGroups
                      groups: item.groups
                      groups_all: groups_all
                      pools_all: servicePools
                      pools: item.pools
                    ))
                    gui.tools.applyCustoms modalId
                    gui.tools.unblockUI()
                    $(modalId + " .button-accept").click ->
                      fields = gui.forms.read(modalId)
                      gui.doLog "Fields", fields
                      group.rest.save fields, ((data) -> # Success on put
                        $(modalId).modal "hide"
                        refreshFnc()
                        gui.notify gettext("Group saved"), "success"
                        return
                      ), gui.failRequestModalFnc("Error saving group", true)
                      return

                    return

                  return

                return

            if value.type is "meta"

              # Meta will get all groups
              group.rest.overview (groups) ->
                exec groups
                return

            else
              exec()
            return

          onNew: (t, table, refreshFnc) ->
            exec = (groups_all) ->
              api.servicesPools.summary (servicePools) ->
                gui.tools.blockUI()
                api.templates.get "group", (tmpl) -> # Get form template
                  # Creates modal
                  if t is "meta"
                    title = gettext("New meta group")
                    servicePools = undefined  # Clear service pools
                  else
                    title = gettext("New group")
                  modalId = gui.launchModal(title, api.templates.evaluate(tmpl,
                    type: t
                    groupname_label: type.groupNameLabel
                    external: type.isExternal
                    canSearchGroups: type.canSearchGroups
                    groups_all: groups_all
                    groups: []
                    pools_all: servicePools
                    pools: []
                  ))
                  gui.tools.unblockUI()
                  gui.tools.applyCustoms modalId
                  searchForm modalId, "group", id, gettext("Search groups"), gettext("Group"), gettext("Groups found") # Enable search button click, if it exist ofc
                  $(modalId + " .button-accept").click ->
                    fields = gui.forms.read(modalId)
                    gui.doLog "Fields", fields
                    group.rest.create fields, ((data) -> # Success on put
                      $(modalId).modal "hide"
                      refreshFnc()
                      gui.notify gettext("Group saved"), "success"
                      return
                    ), gui.failRequestModalFnc(gettext("Group saving error"), true)
                    return

                  return

                return

            if t is "meta"
              # Meta will get all groups
              group.rest.overview (groups) ->
                exec groups
                return

            else
              exec()
            return

          onDelete: gui.methods.del(group, gettext("Delete group"), gettext("Group deletion error"))
        )
        tmpLogTable = null

        # New button will only be shown on authenticators that can create new users
        usrButtons = [
          "edit"
          {
            text: gui.tools.iconAndText( 'fa-info', gettext('Information') )
            css: "disabled"
            disabled: true

            click: (vals, value, btn, tbl, refreshFnc) ->

              if vals.length > 1
                return

              val = vals[0]
              user.rest.invoke val.id + "/servicesPools", (pools) ->
                user.rest.invoke val.id + "/userServices", (userServices) ->
                  user.rest.item val.id, (item) ->
                    group.rest.overview (groups) -> # Get groups
                      gui.doLog "Pools", pools
                      api.templates.get "user-info", (tmpl) ->
                        content = api.templates.evaluate(tmpl,
                          id: 'information',
                          groups_all: groups
                          groups: item.groups
                          pools: pools,
                          userServices: userServices,
                          goClass: 'goLink'
                        )
                        modalId = gui.launchModal(gettext('User information'), content,
                          actionButton: " "
                        )

                        $('#information-groups-table').DataTable(
                          colReorder: true
                          stateSave: true
                          paging: true
                          info: false
                          autoWidth: false
                          lengthChange: false
                          pageLength: 10

                          columnDefs: [
                            { 'width': '100%', 'targets': 0 },
                          ]

                          ordering: true
                          order: [[ 0, 'asc' ]]

                          dom: '<>fr<"uds-table"t>ip'

                          language: gui.config.dataTablesLanguage
                        )


                        $('#information-pools-table').DataTable(
                          colReorder: true
                          stateSave: true
                          paging: true
                          info: false
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

                        $('#information-userservices-table').DataTable(
                          colReorder: true
                          stateSave: true
                          paging: true
                          info: false
                          autoWidth: false
                          lengthChange: false
                          pageLength: 10

                          columnDefs: [
                            { 'width': '25%', 'targets': 0 },
                            { 'width': '25%', 'targets': 1 },
                            { 'width': '120px', 'targets': 2 },
                            { 'width': '20%', 'targets': 3 },
                            { 'width': '20%', 'targets': 4 },
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
              return

          }
          "delete"
          "xls"
        ]
        usrButtons = ["new"].concat(usrButtons)  if type.canCreateUsers # New is first button
        usrTable = user.table(
          icon: 'users'
          container: "users-placeholder"
          doNotLoadData: true
          rowSelect: "multi"
          onRowSelect: (uselected) ->
            gui.doLog 'User row selected ', uselected
            gui.tools.blockUI()
            uId = uselected[0].id
            clearDetailLog()
            tmpLogTable = user.logTable(uId,
              container: "users-log-placeholder"
              onLoad: ->
                detailLogTable = tmpLogTable
                gui.tools.unblockUI()
                return
            )
            return

          onRowDeselect: ->
            clearDetailLog()
            return

          buttons: usrButtons
          deferedRender: true # Use defered rendering for users, this table can be "huge"
          scrollToTable: false
          onLoad: (k) ->
            gui.tools.unblockUI()
            return

          onRefresh: ->
            gui.doLog "Refreshing"
            clearDetailLog()
            return

          onEdit: (value, event, table, refreshFnc) ->
            password = "#æð~¬ŋ@æß”¢€~½¬@#~þ¬@|" # Garbage for password (to detect change)
            gui.tools.blockUI()
            api.templates.get "user", (tmpl) -> # Get form template
              group.rest.overview (groups) -> # Get groups
                user.rest.item value.id, (item) -> # Get item to edit

                  # Creates modal
                  modalId = gui.launchModal(gettext("Edit user") + " <b>" + value.name + "</b>", api.templates.evaluate(tmpl,
                    id: item.id
                    username: item.name
                    username_label: type.userNameLabel
                    realname: item.real_name
                    comments: item.comments
                    state: item.state
                    staff_member: item.staff_member
                    is_admin: item.is_admin
                    needs_password: type.needsPassword
                    password: (if type.needsPassword then password else undefined)
                    password_label: type.passwordLabel
                    groups_all: groups
                    groups: item.groups
                    external: type.isExternal
                    canSearchUsers: type.canSearchUsers
                  ))
                  gui.tools.applyCustoms modalId
                  gui.tools.unblockUI()
                  $(modalId + " .button-accept").click ->
                    fields = gui.forms.read(modalId)

                    # If needs password, and password has changed
                    gui.doLog "passwords", type.needsPassword, password, fields.password
                    delete fields.password  if fields.password is password  if type.needsPassword
                    gui.doLog "Fields", fields
                    user.rest.save fields, ((data) -> # Success on put
                      $(modalId).modal "hide"
                      refreshFnc()
                      gui.notify gettext("User saved"), "success"
                      return
                    ), gui.failRequestModalFnc(gettext("User saving error"), true)
                    return

                  return

                return

              return

            return

          onNew: (undefined_, table, refreshFnc) ->
            gui.tools.blockUI()
            api.templates.get "user", (tmpl) -> # Get form template
              group.rest.overview (groups) -> # Get groups
                # Creates modal
                modalId = gui.launchModal(gettext("New user"), api.templates.evaluate(tmpl,
                  username_label: type.userNameLabel
                  needs_password: type.needsPassword
                  password_label: type.passwordLabel
                  groups_all: groups
                  groups: []
                  external: type.isExternal
                  canSearchUsers: type.canSearchUsers
                ))
                gui.tools.applyCustoms modalId
                gui.tools.unblockUI()
                searchForm modalId, "user", id, gettext("Search users"), gettext("User"), gettext("Users found") # Enable search button click, if it exist ofc
                $(modalId + " .button-accept").click ->
                  fields = gui.forms.read(modalId)

                  # If needs password, and password has changed
                  gui.doLog "Fields", fields
                  user.rest.create fields, ((data) -> # Success on put
                    $(modalId).modal "hide"
                    refreshFnc()
                    gui.notify gettext("User saved"), "success"
                    return
                  ), gui.failRequestModalFnc(gettext("User saving error"), true)
                  return

                return

              return

            return

          onDelete: gui.methods.del(user, gettext("Delete user"), gettext("User deletion error"))
        )
        logTable = gui.authenticators.logTable(id,
          container: "logs-placeholder"
          doNotLoadData: true
        )

        # So we can destroy the tables beforing adding new ones
        prevTables.push grpTable
        prevTables.push usrTable
        prevTables.push logTable
        false

      onNew: gui.methods.typedNew(gui.authenticators, gettext("New authenticator"), gettext("Authenticator creation error"), testButton)
      onEdit: gui.methods.typedEdit(gui.authenticators, gettext("Edit authenticator"), gettext("Authenticator saving error"), testButton)
      onDelete: gui.methods.del(gui.authenticators, gettext("Delete authenticator"), gettext("Authenticator deletion error"))
    )
    return

  false
