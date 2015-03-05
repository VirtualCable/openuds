# jshint strict: true 

# Basic GUI components

# Tools
gui.clear_cache = new BasicGuiElement("Flush cache")
gui.clear_cache.link = ->
  "use strict"

  if api.config.admin is false
    return

  api.getJson "cache/flush",
    success: ->
      gui.launchModal gettext("Cache"), gettext("Cache has been flushed"),
        actionButton: " "

      return

  return