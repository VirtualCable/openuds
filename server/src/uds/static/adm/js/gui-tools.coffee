  "use strict"
  @gui = @gui ? {}
  $ = jQuery
  gui = @gui

  gui.tools =
    blockUI: (message) ->
      message = message or "<h1><span class=\"fa fa-spinner fa-spin\"></span> " + gettext("Just a moment...") + "</h1>"
      $.blockUI message: message
      return

    unblockUI: ->
      $.unblockUI()
      $(".DTTT_collection_background").remove()
      return

    fix3dButtons: (selector) ->
      selector = selector or ""
      selector += " .btn3d"
      $.each $(selector), (index, value) ->
        
        # If no events associated, return
        $this = $(@)
        clkEvents = []
        
        # Store old click events, so we can reconstruct click chain later
        try
          $.each $._data(value, "events").click, (index, fnc) ->
            clkEvents.push fnc
            return
        catch # no events associated ($._data(value, 'events') returns undefined)
          return

        $this.unbind "click"
        
        # If Mousedown registers a temporal mouseUp event on parent, to lauch button click 
        $this.mousedown (event) ->
          $("body").mouseup (e) ->

            # Remove temporal mouseup handler
            $(this).unbind "mouseup"
            
            # If movement of mouse is not too far... (16 px maybe well for 3d buttons?)
            x = event.pageX - e.pageX
            y = event.pageY - e.pageY
            dist_square = x * x + y * y
            if dist_square < 16 * 16
              
              # Register again old event handlers
              $.each clkEvents, (index, fnc) ->
                $this.click fnc.handler
                return

              $this.click()
              $this.unbind "click"
            return

          return

        return

      return

    applyCustoms: (selector) ->
      
      # Activate "custom" styles
      $.each $(selector + " input:checkbox"), (index, tspn) ->
        $tspn = $(tspn)
        if $tspn.attr("basic") != "true"
          $tspn.bootstrapSwitch()

      # datepicker
      $.each $(selector + " input[type=date]:not([readonly])"), (index, tspn) ->
        $tspn = $(tspn)
        if $tspn.val() is '2000-01-01'
          $tspn.val(api.tools.strftime('%Y-01-01'))
        if $tspn.val() is '2099-12-31'
          $tspn.val(api.tools.strftime('%Y-12-31'))

        $tspn.attr("type", "text")

        options =
          format: 'yyyy-mm-dd'
          container: 'html'

        if $tspn.attr('clear') == "true"
          options.clearBtn = true

        $tspn.parent().datepicker options

      # timepicker
      $.each $(selector + " input[type=time]:not([readonly])"), (index, tspn) ->
        $tspn = $(tspn)
        opts = 
          showMeridian: false
          defaultTime: false

        $tspn.timepicker opts

      # Activate "cool" selects
      $.each $(selector + " .selectpicker"), (index, tspn) ->
        $tspn = $(tspn)
        length = $tspn.children('option').length
        if length >= 6
          $tspn.attr("data-live-search", "true")
        $tspn.selectpicker()

      # Activate Touchspinner
      $.each $(selector + " input[type=numeric]:not([readonly])"), (index, tspn) ->
        $tspn = $(tspn)
        minVal = parseInt $tspn.attr("data-minval")
        maxVal = parseInt $tspn.attr("data-maxval")
        if minVal == 987654321
          minVal = -999999
        if maxVal == 987654321
          maxVal = 999999
        gui.doLog minVal
        $tspn.attr("type", "text")
        $tspn.TouchSpin
          verticalbuttons: true
          verticalupclass: 'glyphicon glyphicon-plus'
          verticaldownclass: 'glyphicon glyphicon-minus'
          min: minVal
          max: maxVal
          decimals: 0
        
      # TEST: cooler on mobile devices
      $(selector + " .selectpicker").selectpicker "mobile"  if /Android|webOS|iPhone|iPad|iPod|BlackBerry/i.test(navigator.userAgent)
      
      # Activate tooltips
      $(selector + " [data-toggle=\"tooltip\"]").tooltip
        delay:
          show: 1000
          hide: 100

        placement: "auto right"

      
      # Fix 3d buttons
      gui.tools.fix3dButtons selector
      return

    
    # Datetime renderer (with specified format)
    renderDate: (format) ->
      (data, type, full) ->
        if data == "None" or data is null
          data = 7226578800
          val = gettext('Never')
        else
          val = api.tools.strftime(format, new Date(data * 1000))
        return "<span data-date=\"" + data + "\">" + val + "</span>"

    
    # Log level rendererer
    renderLogLovel: ->
      levels =
        10000: "OTHER"
        20000: "DEBUG"
        30000: "INFO"
        40000: "WARN"
        50000: "ERROR"
        60000: "FATAL"

      (data, type, full) ->
        levels[data] or "OTHER"

  return
