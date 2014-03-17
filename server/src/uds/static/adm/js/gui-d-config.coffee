gui.configuration = new BasicGuiElement("Clear cache")
gui.configuration.link = ->
  "use strict"
  api.templates.get "configuration", (tmpl) ->
    api.configuration.overview ((data) ->
      gui.doLog data
      gui.clearWorkspace()
      gui.appendToWorkspace api.templates.evaluate(tmpl,
        config: data
      )
      gui.setLinksEvents()
      $("#form_config .form-control").each (i, element) ->
        $(element).attr "data-val", $(element).val()
        return

      
      # Add handlers to buttons
      $("#form_config .button-undo").on "click", (event) ->
        fld = $(this).attr("data-fld")
        gui.doLog fld, $("#" + fld).val()
        $("#" + fld).val $("#" + fld).attr("data-val")
        return

      $("#form_config .button-save").on "click", (event) ->
        cfg = {}
        $("#form_config .form-control").each (i, element) ->
          $element = $(element)
          unless $element.attr("data-val") is $element.val()
            section = $element.attr("data-section")
            key = $element.attr("data-key")
            cfg[section] = {}  if cfg[section] is undefined
            cfg[section][key] = value: $element.val()
          return

        gui.doLog cfg
        unless $.isEmptyObject(cfg)
          api.configuration.save cfg, (->
            gui.showDashboard()
            gui.notify gettext("Configuration saved"), "success"
            return
          ), gui.failRequestModalFnc
        return

      return
    ), gui.failRequestModalFnc
    return

  return