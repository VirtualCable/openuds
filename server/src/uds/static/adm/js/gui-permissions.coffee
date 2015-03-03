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

    api.templates.get "permissions", (tmpl) ->
        rest.getPermissions val.id, (data) ->
            id = gui.genRamdonId('perms-')
            content = api.templates.evaluate(tmpl,
                id: id
            )
            modalId = gui.launchModal gettext("Permissions for") + " " + val.name, content,
                actionButton: " "
                closeButton: '<button type="button" class="btn btn-default" data-dismiss="modal">Ok</button>'

            $('#' + id + '_user_del').on('click', () ->
                alert('Del user')
            )

            $('#' + id + '_user_add').on('click', () ->
                addModal yes
            )

            $('#' + id + '_group_del').on('click', () ->
                alert('Del group')
            )

            $('#' + id + '_group_add').on('click', () ->
                addModal no
            )

            # Makes form "beautyfull" :-)
            gui.tools.applyCustoms modalId
