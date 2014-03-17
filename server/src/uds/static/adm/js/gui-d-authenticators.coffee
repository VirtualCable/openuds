# jshint strict: true 
gui.authenticators = new GuiElement(api.authenticators, "auth")
gui.authenticators.link = (event) ->
  "use strict"
  
  # Button definition to trigger "Test" action
  testButton = testButton:
    text: gettext("Test authenticator")
    css: "btn-info"

  
  # Clears the log of the detail, in this case, the log of "users"
  # Memory saver :-)
  detailLogTable = undefined
  clearDetailLog = ->
    if detailLogTable
      $tbl = $(detailLogTable).dataTable()
      $tbl.fnClearTable()
      $tbl.fnDestroy()
      $("#user-log-placeholder").empty()
      detailLogTable = undefined
    return

  
  # Clears the details
  # Memory saver :-)
  prevTables = []
  clearDetails = ->
    $.each prevTables, (undefined_, tbl) ->
      $tbl = $(tbl).dataTable()
      $tbl.fnClearTable()
      $tbl.fnDestroy()
      return

    clearDetailLog()
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
              $select.append "<option value=\"" + value.id + "\">" + value.id + " (" + value.name + ")</option>"
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
      container: "auths-placeholder"
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
        
        # We can have lots of users, so memory can grow up rapidly if we do not keep thins clena
        # To do so, we empty previous table contents before storing new table contents
        # Anyway, TabletTools will keep "leaking" memory, but we can handle a little "leak" that will be fixed as soon as we change the section
        clearDetails()
        $("#detail-placeholder").removeClass "hidden"
        gui.tools.blockUI()
        id = selected[0].id
        type = gui.authenticators.types[selected[0].type]
        gui.doLog "Type", type
        user = new GuiElement(api.authenticators.detail(id, "users"), "users")
        group = new GuiElement(api.authenticators.detail(id, "groups"), "groups")
        grpTable = group.table(
          container: "groups-placeholder"
          rowSelect: "single"
          buttons: [
            "new"
            "edit"
            "delete"
            "xls"
          ]
          onLoad: (k) ->
            gui.tools.unblockUI()
            return

          onEdit: (value, event, table, refreshFnc) ->
            exec = (groups_all) ->
              gui.tools.blockUI()
              api.templates.get "group", (tmpl) -> # Get form template
                group.rest.item value.id, (item) -> # Get item to edit
                  # Creates modal
                  modalId = gui.launchModal(gettext("Edit group") + " <b>" + item.name + "</b>", api.templates.evaluate(tmpl,
                    id: item.id
                    type: item.type
                    groupname: item.name
                    groupname_label: type.groupNameLabel
                    comments: item.comments
                    state: item.state
                    external: type.isExternal
                    canSearchGroups: type.canSearchGroups
                    groups: item.groups
                    groups_all: groups_all
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
              gui.tools.blockUI()
              api.templates.get "group", (tmpl) -> # Get form template
                # Creates modal
                modalId = gui.launchModal(gettext("New group"), api.templates.evaluate(tmpl,
                  type: t
                  groupname_label: type.groupNameLabel
                  external: type.isExternal
                  canSearchGroups: type.canSearchGroups
                  groups: []
                  groups_all: groups_all
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
        tmpLogTable = undefined
        
        # New button will only be shown on authenticators that can create new users
        usrButtons = [
          "edit"
          "delete"
          "xls"
        ]
        usrButtons = ["new"].concat(usrButtons)  if type.canCreateUsers # New is first button
        usrTable = user.table(
          container: "users-placeholder"
          rowSelect: "single"
          onRowSelect: (uselected) ->
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
            $("#users-log-placeholder").empty() # Remove logs on detail refresh
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
        )
        
        # So we can destroy the tables beforing adding new ones
        prevTables.push grpTable
        prevTables.push usrTable
        prevTables.push logTable
        false

      onRefresh: ->
        $("#users-placeholder").empty() # Remove detail on parent refresh
        return

      onNew: gui.methods.typedNew(gui.authenticators, gettext("New authenticator"), gettext("Authenticator creation error"), testButton)
      onEdit: gui.methods.typedEdit(gui.authenticators, gettext("Edit authenticator"), gettext("Authenticator saving error"), testButton)
      onDelete: gui.methods.del(gui.authenticators, gettext("Delete authenticator"), gettext("Authenticator deletion error"))
    )
    return

  false