readParamsFromInputs = (modalId) ->
  a = {}
  for v in $(modalId + ' select.action_parameters,input.action_parameters')
    a[$(v).attr('name')] = $(v).val()
  return a

actionSelectChangeFnc = (modalId, actionsList, context) ->
  action = $(modalId + " #id_action_select").val()
  if action == '-1'
    return
  $(modalId + " #parameters").empty()
  for i in actionsList
    if i['id'] == action
      if i['params'].length > 0
        events = () -> # Empty
        html = ''
        for j in i['params']
          # Transport Type
          if j['type'] == 'transport'
            html += '<div class="form-group"><label for="fld_' + j['name'] +
                    '" class="col-sm-3 control-label">' + j['description'] +
                    '</label><div class="col-sm-9"><select class="selectpicker show-menu-arrow show-tick action_parameters"' +
                    '  name="' + j['name'] + '" data-style="btn-default" data-width="100%" data-live-search="true">';
            # Add transports
            for k in context['transports']
              html += '<option value="' + k['id'] + '"'
              if k['id'] == j['default']
                html += ' selected'
              html += '>' + k['name'] + '</option>'

            html += '</select></div></div>'
          # Group type
          else if j['type'] == 'group'
            # Auths select
            [auth, grp] = if j['default'] != null && '@' in j['default'] then j['default'].split('@') else ['', '']
            html += '<div class="form-group"><label for="fld_authenticator' + j['name'] +
                    '" class="col-sm-3 control-label">' + gettext('Authenticator') +
                    '</label><div class="col-sm-9"><select id="fld_authenticator' + j['name'] + '" class="selectpicker show-menu-arrow show-tick"' +
                    '  name="auth_' + j['name'] + '" data-style="btn-default" data-width="100%" data-live-search="true">';
            # Add authenticators
            for k in context['authenticators']
              html += '<option value="' + k['id'] + '"'
              if k['id'] == auth
                html += ' selected'
              html += '>' + k['name'] + '</option>'
            html += '</select></div></div>'
            # Group selector, filled on event
            html += '<div class="form-group"><label for="fld_' + j['name'] +
                    '" class="col-sm-3 control-label">' + gettext('Group') +
                    '</label><div class="col-sm-9"><select id="fld_group' + j['name'] + '" class="selectpicker show-menu-arrow show-tick action_parameters"' +
                    '  name="' + j['name'] + '" data-style="btn-default" data-width="100%" data-live-search="true">';
            html += '</select></div></div>'

            events = () -> # setup on change and fire it
              authenticatorsElement = modalId + ' #fld_authenticator'+ j['name']
              # Fills up the groups select
              fillGroups = () ->
                authId = $(authenticatorsElement).val()
                api.authenticators.detail(authId, "groups").overview (groups) ->
                  $select = $(modalId + " #fld_group" + j['name'])
                  $select.empty()
                  # Sorts groups, expression means that "if a > b returns 1, if b > a returns -1, else returns 0"
                  maxCL = 32
                  $.each groups, (undefined_, value) ->
                    optVal = authId + '@' + value.id
                    optText = value.name + " (" + value.comments.substr(0, maxCL - 1) + ((if value.comments.length > maxCL then "&hellip;" else ""))
                    gui.doLog('Selected: ', value.id, grp)
                    selected = if grp == value.id then ' selected' else ''
                    $select.append "<option value=\"" + optVal + "\"" + selected + ">" + optText + ")</option>"
                    return

                  # Refresh selectpicker if item is such
                  $select.selectpicker "refresh"  if $select.hasClass("selectpicker")
                  return


              $(authenticatorsElement).on "change", (event) ->
                fillGroups()

              fillGroups()
            
            # Groups select, filled on auths change
          # Default
          else
            html += '<div class="form-group"><label for="fld_' + j['name'] +
                    '" class="col-sm-3 control-label">' + j['description'] +
                    '</label><div class="col-sm-9"><input type="' + j['type'] +
                    '" class="action_parameters" name="' + j['name'] +
                    '" value="' + j['default'] + '"></div></div>'
        $(modalId + " #parameters").html(html)
        events()
        gui.tools.applyCustoms modalId
  return


gui.servicesPools.actionsCalendars = (servPool, info) ->
  actionsApi = api.servicesPools.detail(servPool.id, "actions", { permission: servPool.permission })
  actionsCalendars = new GuiElement(actionsApi, "actions")
  actionsCalendarsTable = null
  # Get transports
  api.transports.overview (oTrans) ->
    api.authenticators.overview (auths) ->
      dctTrans = {}
      trans = []
      # Keep only valid transports for this service pool
      for t in oTrans
          if (t.protocol in servPool.info.allowedProtocols)
            trans.push(t)
            dctTrans[t.id] = t.name

      # Context for "onchange" on new/edit
      context = {'transports': trans, 'authenticators': auths }

      # Now we create the table
      actionsCalendarsTable = actionsCalendars.table(
        doNotLoadData: true
        icon: 'assigned'
        container: "actions-placeholder"
        rowSelect: "multi"
        buttons: [
          "new"
          "edit"
          {
            text: gettext("Launch Now")
            css: "disabled"
            disabled: true
            click: (val, value, btn, tbl, refreshFnc) ->
              if val.length != 1
                return

              gui.forms.confirmModal gettext("Execute action"), gettext("Launch action execution right now?"),
                onYes: ->
                  actionsApi.invoke val[0].id + "/execute", ->
                    refreshFnc()
                    return
              return

            select: (vals, self, btn, tbl, refreshFnc) ->
              unless vals.length == 1
                $(btn).addClass "disabled"
                $(btn).prop('disabled', true)
                return

              val = vals[0]

              $(btn).removeClass("disabled").prop('disabled', false)
              # $(btn).addClass("disabled").prop('disabled', true)
              return
          }
          "delete"
          "xls"
        ]

        onCheck: (action, selected) ->
          if action == 'edit'
            return true
          for v in selected
            if v.id == -1
              return false  # No action allowed on DEFAULT

          return true

        onData: (data) ->
          $.each data, (index, value) ->
            value.atStart = if value.atStart then gettext('Beginning') else gettext('Ending')
            value.calendar = gui.fastLink(value.calendar, value.calendarId, 'gui.servicesPools.fastLink', 'goCalendarLink')

        onNew: (value, table, refreshFnc) ->
          api.templates.get "pool_add_action", (tmpl) ->
            api.calendars.overview (data) ->
              api.servicesPools.actionsList servPool.id, (actionsList) ->
                modalId = gui.launchModal(gettext("Add scheduled action"), api.templates.evaluate(tmpl,
                  calendars: data
                  calendarId: ''
                  actionsList: actionsList
                  action: ''
                  eventsOffset: 0
                  atStart: true
                ))
   
                $(modalId + " .button-accept").on "click", (event) ->
                  offset = $(modalId + " #id_offset").val()
                  calendar = $(modalId + " #id_calendar_select").val()
                  action = $(modalId + " #id_action_select").val()
                  atStart = $(modalId + " #atStart_field").is(":checked")
                  actionsCalendars.rest.create
                    calendarId: calendar
                    action: action
                    eventsOffset: offset
                    atStart: atStart
                    action: action
                    params: readParamsFromInputs(modalId)

                  , (data) ->
                    $(modalId).modal "hide"
                    refreshFnc()
                    return

                  return
                $(modalId + ' #id_action_select').on "change", (event) ->
                  actionSelectChangeFnc(modalId, actionsList, context)
                # Makes form "beautyfull" :-)
                gui.tools.applyCustoms modalId
                return
              return
            return
          return

        onEdit: (value, event, table, refreshFnc) ->
          api.templates.get "pool_add_action", (tmpl) ->
            api.servicesPools.actionsList servPool.id, (actionsList) ->
              actionsCalendars.rest.item value.id, (item) ->
                for i in actionsList
                  if i['id'] == item.action
                    for j in Object.keys(item.params)
                      for k in i['params']
                        if k['name'] == j
                          k['default'] = item.params[j]

                api.calendars.overview (data) ->
                  modalId = gui.launchModal(gettext("Edit access calendar"), api.templates.evaluate(tmpl,
                    calendars: data
                    calendarId: item.calendarId
                    actionsList: actionsList
                    action: item.action
                    eventsOffset: item.eventsOffset
                    atStart: item.atStart
                  ))
                  $(modalId + " .button-accept").on "click", (event) ->
                    offset = $(modalId + " #id_offset").val()
                    calendar = $(modalId + " #id_calendar_select").val()
                    action = $(modalId + " #id_action_select").val()
                    atStart = $(modalId + " #atStart_field").is(":checked")
                    actionsCalendars.rest.save
                      id: item.id
                      calendarId: calendar
                      action: action
                      eventsOffset: offset
                      atStart: atStart
                      action: action
                      params: readParamsFromInputs(modalId)
                    , (data) ->
                      $(modalId).modal "hide"
                      refreshFnc()
                      return
                    return
                  $(modalId + ' #id_action_select').on "change", (event) ->
                    actionSelectChangeFnc(modalId, actionsList, context)

                  # Triggers the event manually
                  actionSelectChangeFnc(modalId, actionsList, context)
                  # Makes form "beautyfull" :-)
                  gui.tools.applyCustoms modalId
                  return
                return
              return
            return
          return
        onDelete: gui.methods.del(actionsCalendars, gettext("Remove access calendar"), gettext("Access calendar removal error"))
      )

  return [actionsCalendarsTable]
