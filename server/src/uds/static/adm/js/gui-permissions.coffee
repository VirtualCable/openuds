gui.permissions = (val, rest, tbl, refreshFnc) ->

    addModal = (forUser) ->
        if forUser
            label = gettext('User')
            items = 'users'
        else
            label = gettext('Group')
            items = 'groups'
        
        api.templates.get "permissions_add", (tmpl) ->
          api.authenticators.overview (data) ->
            # Sorts groups, expression means that "if a > b returns 1, if b > a returns -1, else returns 0"

            modalId = gui.launchModal(gettext("Add") + " " + label, api.templates.evaluate(tmpl,
              auths: data
              label: label
            ))
            $(modalId + " #id_auth_select").on "change", (event) ->
              auth = $(modalId + " #id_auth_select").val()
              api.authenticators.detail(auth, items).overview (data) ->
                $select = $(modalId + " #id_item_select")
                $select.empty()
                # Sorts groups, expression means that "if a > b returns 1, if b > a returns -1, else returns 0"
                $.each data, (undefined_, value) ->
                  $select.append "<option value=\"" + value.id + "\">" + value.name + "</option>"
                  return
                
                # Refresh selectpicker if item is such
                $select.selectpicker "refresh"  if $select.hasClass("selectpicker")
                return

              return

            $(modalId + " .button-accept").on "click", (event) ->
              auth = $(modalId + " #id_auth_select").val()
              item = $(modalId + " #id_item_select").val()
              perm = $(modalId + " #id_perm_select").val()
              if auth is -1 or item is -1
                gui.notify gettext("You must provide authenticator and") + " " + label, "danger"
              else # Save & close modal
                rest.addPermission val.id, items, item, perm
                $(modalId).modal "hide"
              return
            
            # Makes form "beautyfull" :-)
            gui.tools.applyCustoms modalId
            return

    delModal = (forUser, selectedItems) ->
        if forUser
            label = gettext('User')
            items = 'users'
        else
            label = gettext('Group')
            items = 'groups'

        content = '<p>' + gettext("Confirm revocation of following permissions: <br/>")
        content += '<ul style=\'font-family: "Courier New"\'><li>' + ($(v).text() for v in selectedItems).join('</li><li>') + '</li></ul>'
        modalId = gui.launchModal gettext("Remove ") + label + " permission", content,
            actionButton: "<button type=\"button\" class=\"btn btn-primary button-revoke\">" + gettext("Revoke") + "</button>"

        toDel = ($(v).val() for v in selectedItems)

        gui.doLog modalId
        $(modalId + ' .button-revoke').on('click', () ->
            rest.revokePermissions val.id, items, toDel
            $(modalId).modal "hide"
        )

            

    fillSelect = (baseId, perms, forUser) ->
        $select = $('#' + baseId + (if forUser then '_user_select' else '_group_select'))
        $select.empty()

        padRight = (str, len)->
            numPads = len - str.length
            if (numPads > 0) then str + Array(numPads+1).join('&nbsp;') else str

        for item in perms
            if (forUser is true and item.type is 'user') or (forUser is false and item.type is 'group')
                $select.append('<option value="' + item.id + '">' + padRight(item.auth_name + '\\' + item.name, 28) + '&nbsp;| ' + item.perm_name)
                

    api.templates.get "permissions", (tmpl) ->
        rest.getPermissions val.id, (perms) ->
            id = gui.genRamdonId('perms-')
            content = api.templates.evaluate(tmpl,
                id: id
                perms: perms
            )
            modalId = gui.launchModal gettext("Permissions for") + " " + val.name, content,
                actionButton: " "
                closeButton: '<button type="button" class="btn btn-default" data-dismiss="modal">Ok</button>'

            # Fills user select
            fillSelect id, perms, true
            fillSelect id, perms, false


            $('#' + id + '_user_del').on('click', () ->
                $select = $('#' + id + '_user_select')
                selected = $select.find(":selected")
                return if selected.length is 0

                delModal true, selected
            )

            $('#' + id + '_user_add').on('click', () ->
                addModal yes
            )

            $('#' + id + '_group_del').on('click', () ->
                $select = $('#' + id + '_group_select')
                selected = $select.find(":selected")
                return if selected.length is 0

                delModal false, selected
            )

            $('#' + id + '_group_add').on('click', () ->
                addModal no
            )

            # Makes form "beautyfull" :-)
            gui.tools.applyCustoms modalId
