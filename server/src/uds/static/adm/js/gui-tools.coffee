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
      $(selector + " input:checkbox").bootstrapSwitch()
      
      # Activate "cool" selects
      $(selector + " .selectpicker").selectpicker()

      # Activate Touchspinner
      $(selector + " input[type=numeric]:not([readonly])").TouchSpin
        min: 0
        max: 99999
        decimals: 0
        
      $(selector + " input[type=numeric]:not([readonly])").attr("type", "text")
      
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
        "<span data-date=\"" + data + "\">" + api.tools.strftime(format, new Date(data * 1000)) + "</span>"

    
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
