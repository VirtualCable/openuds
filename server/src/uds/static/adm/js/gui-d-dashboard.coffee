gui.dashboard = new BasicGuiElement("Dashboard")
gui.dashboard.link = (event) ->
  "use strict"
  gui.clearWorkspace()
  api.templates.get "dashboard", (tmpl) ->
    api.system.overview (data) ->
      gui.doLog "enter dashboard"
      gui.appendToWorkspace api.templates.evaluate(tmpl,
        users: data.users
        services: data.services
        user_services: data.user_services
        restrained_services_pools: data.restrained_services_pools
      )
      gui.setLinksEvents()
      $.each [
        "assigned"
        "inuse"
      ], (index, stat) ->
        api.system.stats stat, (data) ->
          d = []
          $.each data, (index, value) ->
            d.push [
              value.stamp * 1000
              value.value
            ]
            return

          gui.doLog "Data", d
          $.plot "#placeholder-" + stat + "-chart", [d],
            xaxis:
              mode: "time"
              timeformat: api.tools.djangoFormat(django.formats.SHORT_DATE_FORMAT)

          return

        return

      return

    return

  return