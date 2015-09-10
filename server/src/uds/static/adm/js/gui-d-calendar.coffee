gui.calendars = new GuiElement(api.calendars, "imgal")
gui.calendars.link = ->
  "use strict"

  rulesTable = undefined
  clearRules = ->
    if rulesTable
      $tbl = $(rulesTable).dataTable()
      $tbl.fnClearTable()
      $tbl.fnDestroy()
      rulesTable = undefined
    $("#rules-placeholder").empty()
    $("#detail-placeholder").addClass "hidden"
    return

  freqDct =
    'DAILY': [gettext('day'), gettext('days')]
    'WEEKLY': [gettext('week'), gettext('weeks')]
    'MONTHLY': [gettext('month'), gettext('months')]
    'YEARLY': [gettext('year'), gettext('years')]

  weekDays = [
    gettext('Sun'), gettext('Monday'), gettext('Tuesday'), gettext('Wednesday'), gettext('Thursday'), gettext('Friday'), gettext('Saturday')
  ]

  converter = (fld, data, type, record) ->
    # Display "custom" fields of rules table
    if fld == "interval"
      if record.frequency == "WEEKDAYS"
        res = []
        for i in [0..6]
          if data & 1 != 0
            res.push(weekDays[i].substr(0,3))
          data >>= 1
        return res.join(",")
      try
        return data + " " + freqDct[record.frequency][pluralidx(data)]
      catch e
        return e
    else if fld == "duration"
      if data < 60
        return data + " " + gettext('minutes')
      else
        return Math.floor(data/60) + ":" + ("00" + data%60).slice(-2) + " " + gettext("hours")
    return fld
    
    

  api.templates.get "calendars", (tmpl) ->
    gui.clearWorkspace()
    gui.appendToWorkspace api.templates.evaluate(tmpl,
      calendars: "calendars-placeholder"
      rules: "rules-placeholder"
    )
    gui.calendars.table
      icon: 'calendars'
      container: "calendars-placeholder"
      rowSelect: "single"
      onRowSelect: (selected) ->
        clearRules()
        $("#detail-placeholder").removeClass "hidden"
        # gui.tools.blockUI()
        id = selected[0].id
        rules = new GuiElement(api.calendars.detail(id, "rules", { permission: selected[0].permission }), "rules")
        rulesTable = rules.table(
          icon: 'calendars'
          callback: converter
          container: "rules-placeholder"
          rowSelect: "single"
          buttons: [
            "new"
            "edit"
            "delete"
            "xls"
          ]
          onLoad: (k) ->
            # gui.tools.unblockUI()
            return # null return
        )
        return

      onRowDeselect: ->
        clearRules()
        return
      buttons: [
        "new"
        "edit"
        "delete"
        "xls"
        "permissions"
      ]
      onNew: gui.methods.typedNew(gui.calendars, gettext("New calendar"), gettext("Calendar creation error"))
      onEdit: gui.methods.typedEdit(gui.calendars, gettext("Edit calendar"), gettext("Calendar saving error"))
      onDelete: gui.methods.del(gui.calendars, gettext("Delete calendar"), gettext("Calendar deletion error"))
