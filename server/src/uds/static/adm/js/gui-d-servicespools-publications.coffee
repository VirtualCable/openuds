gui.servicesPools.publications = (servPool, info) ->
  pubApi = api.servicesPools.detail(servPool.id, "publications", { permission: servPool.permission })
  publications = new GuiElement(pubApi, "publications")

  # Publications table
  publicationsTable = publications.table(
    doNotLoadData: true
    icon: 'publications'
    container: "publications-placeholder_tbl"
    doNotLoadData: true
    rowSelect: "single"
    buttons: [
      "new"
      {
        text: gettext("Cancel")
        css: "disabled"
        disabled: true
        click: (val, value, btn, tbl, refreshFnc) ->
          gui.doLog val, val[0]
          gui.forms.confirmModal gettext("Publish"), gettext("Cancel publication?"),
            onYes: ->
              pubApi.invoke val[0].id + "/cancel", ->
                refreshFnc()
                return

              return

          return

        select: (vals, self, btn, tbl, refreshFnc) ->
          unless vals.length == 1
            $(btn).addClass "disabled"
            $(btn).prop('disabled', true)
            return

          val = vals[0]

          if val.state == 'K'
            $(btn).empty().append(gettext("Force Cancel"))
          else
            $(btn).empty().append(gettext("Cancel"))

          # Waiting for publication, Preparing or running
          gui.doLog "State: ", val.state
          if ["P", "W", "L", "K"].indexOf(val.state) != -1
            $(btn).removeClass("disabled").prop('disabled', false)
          else
            $(btn).addClass("disabled").prop('disabled', true)

          return
      }
      "xls"
    ]
    onNew: (action, tbl, refreshFnc) ->
        # Ask for "reason" for publication
      api.templates.get "publish", (tmpl) ->
        content = api.templates.evaluate(tmpl,
        )
        modalId = gui.launchModal(gettext("Publish"), content,
          actionButton: "<button type=\"button\" class=\"btn btn-success button-accept\">" + gettext("Publish") + "</button>"
        )
        gui.tools.applyCustoms modalId
        $(modalId + " .button-accept").click ->
          chlog = encodeURIComponent($('#id_publish_log').val())
          $(modalId).modal "hide"
          pubApi.invoke "publish", (->
            refreshFnc()
            changelog.refresh()
            # Also changelog
            return
          ),
          gui.failRequestModalFnc(gettext("Failed creating publication")),
          { params: 'changelog=' + chlog }

        return

      return
  )

  # changelog
  clApi = api.servicesPools.detail(servPool.id, "changelog")
  changelog = new GuiElement(clApi, "changelog", { permission: servPool.permission })
  clTable = changelog.table(
    icon: 'publications'
    doNotLoadData: true
    container: "changelog-placeholder"
    rowSelect: "single"
  )

  return [publicationsTable, clTable]
