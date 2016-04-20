gui.servicesPools.transports = (servPool, info) ->
  transports = new GuiElement(api.servicesPools.detail(servPool.id, "transports", { permission: servPool.permission }), "transports")

  # Transports items table
  transportsTable = transports.table(
    doNotLoadData: true
    icon: 'transports'
    container: "transports-placeholder"
    doNotLoadData: true
    rowSelect: "multi"
    buttons: [
      "new"
      "delete"
      "xls"
    ]
    onNew: (value, table, refreshFnc) ->
      api.templates.get "pool_add_transport", (tmpl) ->
        api.transports.overview (data) ->
          gui.doLog "Data Received: ", servPool, data
          valid = []
          for i in data
            if (i.protocol in servPool.info.allowedProtocols)
              valid.push(i)
          modalId = gui.launchModal(gettext("Add transport"), api.templates.evaluate(tmpl,
            transports: valid
          ))
          $(modalId + " .button-accept").on "click", (event) ->
            transport = $(modalId + " #id_transport_select").val()
            if transport is -1
              gui.notify gettext("You must provide a transport"), "danger"
            else # Save & close modal
              transports.rest.create
                id: transport
              , (data) ->
                $(modalId).modal "hide"
                refreshFnc()
                return

            return


          # Makes form "beautyfull" :-)
          gui.tools.applyCustoms modalId
          return

        return

      return

    onDelete: gui.methods.del(transports, gettext("Remove transport"), gettext("Transport removal error"))
    onData: (data) ->
      $.each data, (undefined_, value) ->
        style = "display:inline-block; background: url(data:image/png;base64," + value.type.icon + "); ; background-size: 16px 16px; background-repeat: no-repeat; width: 16px; height: 16px; vertical-align: middle;"
        value.trans_type = value.type.name
        value.name = gui.fastLink("<span style=\"" + style + "\"></span> #{value.name}", value.id, 'gui.servicesPools.fastLink', 'goTransportLink')
        return

      return
  )
  return [transportsTable]
