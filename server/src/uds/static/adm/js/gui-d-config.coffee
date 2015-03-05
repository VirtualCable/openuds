gui.configuration = new BasicGuiElement("Clear cache")
gui.configuration.link = ->
  "use strict"

  if api.config.admin is false
    return

  api.templates.get "configuration", (tmpl) ->
    api.configuration.overview ((data) ->
      gui.doLog data
      gui.clearWorkspace()
      gui.appendToWorkspace api.templates.evaluate(tmpl,
        config: data
      )
      gui.setLinksEvents()
      gui.tools.applyCustoms "#form_config"
      for element in $("#form_config .config-ctrl")
        $element = $(element)
        val = if $element.attr('type') is 'checkbox' then (if $element.is(":checked") then "1" else "0") else $element.val()
        $element.attr "data-val", val

      
      # Add handlers to buttons
      $("#form_config .button-undo").on "click", (event) ->
        fld = $(this).attr("data-fld")
        gui.doLog fld, $("#" + fld).val()
        $("#" + fld).val $("#" + fld).attr("data-val")
        return

      $("#form_config .button-save").on "click", (event) ->
        cfg = {}
        for element, i in $("#form_config .config-ctrl")
          # $("#form_config .form-control").each (i, element) ->
          $element = $(element)
          val = if $element.attr('type') is 'checkbox' then (if $element.is(":checked") then "1" else "0") else $element.val()
          unless $element.attr("data-val") is val
            section = $element.attr("data-section")
            key = $element.attr("data-key")
            cfg[section] = {}  if not cfg[section]?
            cfg[section][key] = value: val

        gui.doLog cfg
        unless $.isEmptyObject(cfg)
          api.configuration.save cfg, (->
            gui.showDashboard()
            gui.notify gettext("Configuration saved"), "success"
            return
          ), gui.failRequestModalFnc
        else
          gui.showDashboard()
          gui.notify gettext("No changes has been made"), "success"
          return
        return

      return
    ), gui.failRequestModalFnc
    return

  return