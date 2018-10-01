gui.metaPools.accessCalendars = (metaPool, info) ->
  accessList = ['ALLOW', 'DENY']
  accessCalendars = new GuiElement(api.metaPools.detail(metaPool.id, "access", { permission: metaPool.permission }), "access")
  accessCalendarsTable = accessCalendars.table(
    doNotLoadData: true
    icon: 'assigned'
    container: "access-placeholder"
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

    onData: (data) ->
      $.each data, (index, value) ->
         # value.calendar = "<a href='##{value.calendarId}' class='goCalendarLink'>#{value.calendar}</a>"
         value.calendar = gui.fastLink(value.calendar, value.calendarId, 'gui.metaPools.fastLink', 'goCalendarLink')
      data.push
        id: -1,
        calendar: '-',
        priority: '<span style="visibility: hidden;font-size: 0px;">10000000</span>FallBack',
        access: metaPool.fallbackAccess
      gui.doLog data

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
              access: metaPool.fallbackAccess
            ))
            $(modalId + " .button-accept").on "click", (event) ->
              access = $(modalId + " #id_access_select").val()
              metaPool.fallbackAccess = access
              gui.metaPools.rest.setFallbackAccess metaPool.id, access, (data) ->
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
