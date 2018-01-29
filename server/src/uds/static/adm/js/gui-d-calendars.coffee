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
    'DAILY': [gettext('day'), gettext('days'), gettext('Daily')]
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

  dateFormat = api.tools.djangoFormat(get_format("SHORT_DATE_FORMAT"))

  getWeekDays = (bits, full) ->
    res = []
    for i in [0..6]
      if bits & 1 != 0
        if full is undefined
            res.push(weekDays[i].substr(0,3))
        else
            res.push(weekDays[i])
      bits >>= 1
    if res.length == 0
        return gettext("(no days)")
    return res.join(', ')

  renderer = (fld, data, type, record) ->
    # Display "custom" fields of rules table
    if fld == "interval"
      if record.frequency == "WEEKDAYS"
        return getWeekDays data
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

    readFields = (modalId) ->
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
        duration: parseInt(values.rule_duration)
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
        data.interval = parseInt(values.rule_interval)

      return data

    updateSummary = (modalId) ->
      $summary = $('#summary')
      data = readFields modalId
      txt = gettext("This rule will be valid every ")

      if data.frequency == 'WEEKDAYS'
        txt += getWeekDays(data.interval, true) + " " + gettext("of any week")
      else
        n = if data.interval != 1 then 1 else 0
        interval = if n == 0 then "" else data.interval
        units = freqDct[data.frequency][n]
        txt += "#{interval} #{units}"

      startDate =  new Date(data.start * 1000)
      txt += ", " + gettext("from") + " " + api.tools.strftime(dateFormat, startDate)
      if data.end == null
        txt += " " + gettext("onwards")
      else
        txt += " " + gettext("until ") + api.tools.strftime(dateFormat, new Date(data.end * 1000))

      txt += ", " + gettext("starting at") + " " + startDate.toTimeString().split(':')[0..1].join(':') + " "

      if data.duration > 0
        dunit = dunitDct[data.duration_unit]
        txt += gettext("and will remain valid for") + "#{data.duration} #{dunit}"
      else
        txt += gettext("with no duration")


      $summary.html(txt)

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
        else
            now = Math.floor(new Date().getTime() / 1000)
            fillDateTime '#id-rule-start', now



        #
        # apply styles
        #
        gui.tools.applyCustoms modalId

        # update summary
        updateSummary modalId

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

        # To update summary
        $(modalId + ' input').on('change', () ->
            updateSummary modalId
        )

        $(modalId + ' select').on('change', () ->
            updateSummary modalId
        )

        $form = $(modalId + " form")

        $form.validate
          debug: false
          ignore: ':hidden:not("select"):not(".modal_field_data")'
          errorClass: "text-danger"
          validClass: "has-success"
          focusInvalid: true
          highlight: (element) ->
            group = $(element).closest(".form-group")
            group.addClass "has-error"
            return

          showErrors: (errorMap, errorList) ->
            this.defaultShowErrors()

          success: (element) ->
            $(element).closest(".form-group").removeClass "has-error"
            $(element).remove()
            return

        # Save
        $(modalId + " .button-accept").click ->
          return unless $form.valid()

          data = readFields modalId

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

      onRefresh: (tbl) ->
        clearRules()
        return

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
          rowSelect: "multi"
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
