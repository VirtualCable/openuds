gui.calendars = new GuiElement(api.calendars, "calendars")
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
    'DAILY': [gettext('day'), gettext('days'), gettext('Dayly')]
    'WEEKLY': [gettext('week'), gettext('weeks'), gettext('Weekly')]
    'MONTHLY': [gettext('month'), gettext('months'), gettext('Monthly')]
    'YEARLY': [gettext('year'), gettext('years'), gettext('Yearly')]
    'WEEKDAYS': ['', '', gettext('Weekdays')]

  dunitDct = 
    'MINUTES': gettext('Minutes')
    'HOURS': gettext('Hours')
    'DAYS': gettext('Days')
    'WEEKS': gettext('Weeks')

  weekDays = [
    gettext('Sun'), gettext('Monday'), gettext('Tuesday'), gettext('Wednesday'), gettext('Thursday'), gettext('Friday'), gettext('Saturday')
  ]

  renderer = (fld, data, type, record) ->
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
        return data + " " + dunitDct[record.duration_unit]
    return fld
    
  newEditFnc = (rules, forEdit) ->
    days = (w.substr(0, 3) for w in weekDays)
    sortFnc = (a, b) ->
      return 1 if a.value > b.value
      return -1 if a.value < b.value
      return 0

    fillDateTime = (idDate, stamp) ->
      if stamp is null
        return
      date = new Date(stamp * 1000)
      $(idDate).val(api.tools.strftime('%Y-%m-%d', date))
      $(idDate + "-time").val(date.toTimeString().split(':')[0..1].join(':'))

    getDateTime = (idDate, withoutTime) ->
      date = $(idDate).val()
      if date == '' or date == null
        return null

      if withoutTime is undefined
        time = $(idDate + '-time').val()
        return api.tools.input2timeStamp(date, time)
      else
        return apit.tools.input2timeStamp(date)

    realFnc = (value, refreshFnc) ->
      api.templates.get "calendar_rule", (tmpl) ->
        content = api.templates.evaluate(tmpl,
            freqs: ( {id: key, value: val[2]} for own key, val of freqDct)
            dunits: ( {id: key, value: val} for own key, val of dunitDct)
            days: days
        )
        modalId = gui.launchModal((if value is null then gettext("New rule") else gettext("Edit rule") + ' <b>' + value.name + '</b>' ), content,
          actionButton: "<button type=\"button\" class=\"btn btn-success button-accept\">" + gettext("Save") + "</button>"
        )

        $('#div-interval').show()
        $('#div-weekdays').hide()

        #
        # Fill in fields if needed (editing)
        #
        if value != null
          gui.doLog "Value: ", value
          $('#id-rule-name').val(value.name)
          $('#id-rule-comments').val(value.comments)
          fillDateTime '#id-rule-start', value.start
          fillDateTime '#id-rule-end', value.end
          $('#id-rule-duration').val(value.duration)
          $('#id-rule-duration-unit').val(value.duration_unit)

          # If weekdays, set checkboxes
          $('#id-rule-freq').val(value.frequency)

          if value.frequency == 'WEEKDAYS'
            $('#div-interval').hide()
            $('#div-weekdays').show()

            gui.doLog "Interval", value.interval
            n = value.interval
            # Set up Weekdays
            for i in [0..6]
              if n & 1 != 0
                chk = $('#rule-wd-'+days[i])
                chk.prop('checked', true)
                chk.parent().addClass('active')
              n >>= 1
          else
            $('#id-rule-interval-num').val(value.interval)
            n = if parseInt($('#id-rule-interval-num').val()) != 1 then 1 else 0
            $("#id-rule-interval-num").attr('data-postfix', freqDct[value.frequency][n])


        #
        # apply styles
        #
        gui.tools.applyCustoms modalId

        # And adjust interval spinner

        #
        # Event handlers
        #

        # Change frequency
        $('#id-rule-freq').on 'change', () ->
          $this = $(this)
          if $this.val() == "WEEKDAYS"
            $('#div-interval').hide()
            $('#div-weekdays').show()
          else
            $('#div-interval').show()
            $('#div-weekdays').hide()

          n = if parseInt($('#id-rule-interval-num').val()) != 1 then 1 else 0
          $(modalId + ' .bootstrap-touchspin-postfix').html(freqDct[$this.val()][n])
          return

        $('#id-rule-interval-num').on 'change', () ->
          n = if parseInt($('#id-rule-interval-num').val()) != 1 then 1 else 0
          $(modalId + ' .bootstrap-touchspin-postfix').html(freqDct[$('#id-rule-freq').val()][n])
          return


        # Save
        $(modalId + " .button-accept").click ->

          value = { id: '' } if value is null

          values = {}

          $(modalId + ' :input').each ()->
            values[this.name] = $(this).val()
            return

          $(modalId + ' :input[type=checkbox]').each ()->
            values[this.name] = $(this).prop('checked')
            return

          data =
            name: values.rule_name
            comments: values.rule_comments
            frequency: values.rule_frequency
            start: getDateTime('#id-rule-start')
            end: getDateTime('#id-rule-end')
            duration: values.rule_duration
            duration_unit: values.rule_duration_unit

          if $('#id-rule-freq').val() == 'WEEKDAYS'
            n = 1
            val = 0
            for i in [0..6]
              if values['wd_'+days[i]] is true
                val += n
              n <<= 1
            data.interval = val
          else
            data.interval = values.rule_interval

          closeAndRefresh = () ->
            $(modalId).modal "hide"
            refreshFnc()

          if value is null
            rules.rest.create data, closeAndRefresh, gui.failRequestModalFnc(gettext('Error creating rule'), true)
          else
            data.id = value.id
            rules.rest.save data, closeAndRefresh, gui.failRequestModalFnc(gettext('Error saving rule'), true)

          gui.doLog value, data


    if forEdit is true
      (value, event, table, refreshFnc) ->
        realFnc value, refreshFnc
    else
      (meth, table, refreshFnc) ->
        realFnc null, refreshFnc


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
          callback: renderer
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
          onNew: newEditFnc rules, false
          onEdit: newEditFnc rules, true
          onDelete: gui.methods.del(rules, gettext("Delete rule"), gettext("Rule deletion error"))

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
