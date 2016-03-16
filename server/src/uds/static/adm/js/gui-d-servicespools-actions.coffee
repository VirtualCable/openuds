gui.servicesPools.actionsCalendars = (servPool, info) ->
  accessCalendars = new GuiElement(api.servicesPools.detail(servPool.id, "actions", { permission: servPool.permission }), "actions")
  accessCalendarsTable = accessCalendars.table(
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
          modalId = gui.launchModal(gettext("Add access calendar"), api.templates.evaluate(tmpl,
            calendars: data
            priority: 1
            calendarId: ''
            accessList: accessList
            access: 'ALLOW'
          ))
          $(modalId + " .button-accept").on "click", (event) ->
            priority = $(modalId + " #id_priority").val()
            calendar = $(modalId + " #id_calendar_select").val()
            access = $(modalId + " #id_access_select").val()
            accessCalendars.rest.create
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
        accessCalendars.rest.item value.id, (item) ->
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
              accessCalendars.rest.save
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

    onDelete: gui.methods.del(accessCalendars, gettext("Remove access calendar"), gettext("Access calendar removal error"))
  )

  return [accessCalendarsTable]
