gui.servicesPools.actionsCalendars = (servPool, info) ->
  actionsCalendars = new GuiElement(api.servicesPools.detail(servPool.id, "actions", { permission: servPool.permission }), "actions")
  actionsCalendarsTable = actionsCalendars.table(
    doNotLoadData: true
    icon: 'assigned'
    container: "actions-placeholder"
    rowSelect: "multi"
    buttons: [
      "new"
      "edit"
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

    onNew: (value, table, refreshFnc) ->
      api.templates.get "pool_add_access", (tmpl) ->
        api.calendars.overview (data) ->
          api.servicesPools.actionsList servPool.id, (actionsList) ->
            modalId = gui.launchModal(gettext("Add scheduled action"), api.templates.evaluate(tmpl,
              calendars: data
              priority: 1
              calendarId: ''
              actionsList: actionsList
              action: ''
              eventOffset: 0
              atStart: true
            ))
            $(modalId + " .button-accept").on "click", (event) ->
              priority = $(modalId + " #id_priority").val()
              calendar = $(modalId + " #id_calendar_select").val()
              action = $(modalId + " #id_action_select").val()
              actionsCalendars.rest.create
                calendarId: calendar
                action: action
                priority: priority
              , (data) ->
                $(modalId).modal "hide"
                refreshFnc()
                return

              return
            $(modalId + ' #id_action_select').on "change", (event) ->
              action = $(modalId + " #id_action_select").val()
              if action == '-1'
                return
              $(modalId + " #parameters").empty()
              for i in actionsList
                if i['id'] == action
                  if i['params'].length > 0
                    html = ''
                    for j in i['params']
                      if j['type'] == 'numeric'
                        defval = '1'
                      else
                        defval = ''
                      html += '<div class="form-group"><label for="fld_' + j['name'] + '" class="col-sm-3 control-label">' + j['description'] + '</label><div class="col-sm-9"><input type="' + j['type'] + '" class="modal_field_data" id="fld_' + j['name'] + '" value="' + defval + '"></div></div>'
                    $(modalId + " #parameters").html(html)
                    gui.tools.applyCustoms modalId
              return
            # Makes form "beautyfull" :-)
            gui.tools.applyCustoms modalId
            return
          return
        return
      return

    onEdit: (value, event, table, refreshFnc) ->
      if value.id == -1
        api.templates.get "pool_access_default", (tmpl) ->
            modalId = gui.launchModal(gettext("Default fallback access"), api.templates.evaluate(tmpl,
              accessList: accessList
              access: servPool.fallbackAccess
            ))
            $(modalId + " .button-accept").on "click", (event) ->
              access = $(modalId + " #id_access_select").val()
              servPool.fallbackAccess = access
              gui.servicesPools.rest.setFallbackAccess servPool.id, access, (data) ->
                $(modalId).modal "hide"
                refreshFnc()
                return
            # Makes form "beautyfull" :-)
            gui.tools.applyCustoms modalId
        return
      api.templates.get "pool_add_access", (tmpl) ->
        actionsCalendars.rest.item value.id, (item) ->
          api.calendars.overview (data) ->
            gui.doLog "Item: ", item
            modalId = gui.launchModal(gettext("Edit access calendar"), api.templates.evaluate(tmpl,
              calendars: data
              priority: item.priority
              calendarId: item.calendarId
              accessList: accessList
              access: item.access
            ))
            $(modalId + " .button-accept").on "click", (event) ->
              priority = $(modalId + " #id_priority").val()
              calendar = $(modalId + " #id_calendar_select").val()
              access = $(modalId + " #id_access_select").val()
              actionsCalendars.rest.save
                id: item.id
                calendarId: calendar
                access: access
                priority: priority
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

    onDelete: gui.methods.del(actionsCalendars, gettext("Remove access calendar"), gettext("Access calendar removal error"))
  )

  return [actionsCalendarsTable]
