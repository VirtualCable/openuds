readParamsFromInputs = (modalId) ->
  a = {}
  a[$(v).attr('name')] = $(v).val() for v in $(modalId + ' .action_parameters')
  return a

actionSelectChangeFnc = (modalId, actionsList) ->
  gui.doLog "onChange"
  action = $(modalId + " #id_action_select").val()
  if action == '-1'
    return
  $(modalId + " #parameters").empty()
  for i in actionsList
    if i['id'] == action
      if i['params'].length > 0
        html = ''
        for j in i['params']
          html += '<div class="form-group"><label for="fld_' + j['name'] +
                  '" class="col-sm-3 control-label">' + j['description'] +
                  '</label><div class="col-sm-9"><input type="' + j['type'] +
                  '" class="action_parameters" name="' + j['name'] +
                  '" value="' + j['default'] + '"></div></div>'
        $(modalId + " #parameters").html(html)
        gui.tools.applyCustoms modalId
  return


gui.servicesPools.actionsCalendars = (servPool, info) ->
  actionsApi = api.servicesPools.detail(servPool.id, "actions", { permission: servPool.permission })
  actionsCalendars = new GuiElement(actionsApi, "actions")
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

          gui.doLog val, val[0]
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
        value.params = ( k + "=" + value.params[k] for k in Object.keys(value.params)).toString()
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
              actionSelectChangeFnc(modalId, actionsList)
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
                gui.doLog "Found ", i
                for j in Object.keys(item.params)
                  gui.doLog "Testing ", j
                  for k in i['params']
                    gui.doLog 'Checking ', k
                    if k['name'] == j
                      gui.doLog 'Setting value'
                      k['default'] = item.params[j]

            api.calendars.overview (data) ->
              gui.doLog "Item: ", item
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
                actionSelectChangeFnc(modalId, actionsList)

              # Triggers the event manually
              actionSelectChangeFnc(modalId, actionsList)
              # Makes form "beautyfull" :-)
              gui.tools.applyCustoms modalId
              return
            return
          return
        return

    onDelete: gui.methods.del(actionsCalendars, gettext("Remove access calendar"), gettext("Access calendar removal error"))
  )

  return [actionsCalendarsTable]
