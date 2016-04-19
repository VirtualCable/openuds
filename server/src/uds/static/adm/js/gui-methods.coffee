# Generic "methods" for editing, creating, etc...
gui.methods = {}
gui.methods.typedTestButton = (rest, text, css, type) ->
  [
    text: text
    css: css
    action: (event, form_selector, closeFnc) ->
      fields = gui.forms.read(form_selector)
      gui.doLog "Fields: ", fields
      rest.test type, fields, ((data) ->
        if data == 'ok'
          text = gettext("Test passed successfully")
          kind = 'success'
        else
          text = gettext("Test failed:") + " #{data}</b>"
          kind = 'danger'
        gui.notify text, kind
        # gui.launchModal gettext("Test result"), text,
        #  actionButton: " "

        return
      ), gui.failRequestModalFnc(gettext("Test error"))
      return
  ]

# "Generic" edit method to set onEdit table
gui.methods.typedEdit = (parent, modalTitle, modalErrorMsg, options) ->
  options = options or {}
  (value, event, table, refreshFnc) ->
    gui.tools.blockUI()
    parent.rest.gui value.type, ((guiDefinition) ->
      buttons = gui.methods.typedTestButton(parent.rest, options.testButton.text, options.testButton.css, value.type)  if options.testButton
      tabs = (if options.guiProcessor then options.guiProcessor(guiDefinition) else guiDefinition) # Preprocess fields (probably generate tabs...)
      parent.rest.item value.id, (item) ->
        gui.tools.unblockUI()
        gui.forms.launchModal
          title: modalTitle + " <b>" + value.name + "</b>"
          fields: tabs
          item: item
          preprocessor: options.preprocessor
          buttons: buttons
          success: (form_selector, closeFnc) ->
            fields = gui.forms.read(form_selector)
            fields.data_type = value.type
            fields = (if options.fieldsProcessor then options.fieldsProcessor(fields) else fields)
            parent.rest.save fields, ((data) -> # Success on put
              closeFnc()
              refreshFnc()
              gui.notify gettext("Edition successfully done"), "success"
              return
            ), gui.failRequestModalFnc(modalErrorMsg, true) # Fail on put, show modal message
            return

        return

      return
    ), gui.failRequestModalFnc(modalErrorMsg, true)
    return

gui.methods.typedShow = (parent, value, placeholder, modalErrorMsg, options) ->
  options = options or {}
  parent.rest.gui value.type, ((guiDefinition) ->
    formId = gui.genRamdonId('ovw-')
    parent.rest.item value.id, (item) ->
      gui.doLog "Item", item, "Gui", guiDefinition
      data = []
      # flds = gui.forms.fieldsToHtml(guiDefinition, item, "readonly")
      flds = gui.forms.fromFields(guiDefinition, item, true)
      gui.doLog(flds)
      html = api.templates.evaluate "tmpl_comp_overview_record",
        id: formId
        legend: gettext('Overview')
        fields: flds.html
      $(placeholder).html(html)
      flds.init('#' + formId)
      gui.tools.applyCustoms '#' + formId
    return
    ), gui.failRequestModalFnc(modalErrorMsg, true)
  return


# "Generic" new method to set onNew table
gui.methods.typedNew = (parent, modalTitle, modalErrorMsg, options) ->
  options = options or {}
  (type, table, refreshFnc) ->
    gui.tools.blockUI()
    parent.rest.gui type, ((guiDefinition) ->
      gui.tools.unblockUI()
      buttons = gui.methods.typedTestButton(parent.rest, options.testButton.text, options.testButton.css, type)  if options.testButton
      tabs = (if options.guiProcessor then options.guiProcessor(guiDefinition) else guiDefinition) # Preprocess fields (probably generate tabs...)
      title = modalTitle
      title += " " + gettext("of type") + " <b>" + parent.types[type].name + "</b>"  if parent.types[type]?
      gui.forms.launchModal
        title: title
        fields: tabs
        item: null
        preprocessor: options.preprocessor
        buttons: buttons
        success: (form_selector, closeFnc) ->
          fields = gui.forms.read(form_selector)
          fields.data_type = type  if parent.types[type]?
          fields = (if options.fieldsProcessor then options.fieldsProcessor(fields) else fields) # Process fields before creating?
          parent.rest.create fields, ((data) -> # Success on put
            closeFnc()
            refreshFnc()
            gui.notify gettext("Creation successfully done"), "success"
            return
          ), gui.failRequestModalFnc(modalErrorMsg, true) # Fail on put, show modal message
          return

      return
    ), gui.failRequestModalFnc(modalErrorMsg, true)
    return

gui.methods.del = (parent, modalTitle, modalErrorMsg) ->
  (values, type, table, refreshFnc) ->
    names = ((value.name or value.friendly_name) for value in values).join(', ')
    content = gettext("Are you sure do you want to delete ") + values.length + ' ' + gettext('items:') + " <b>" + names + "</b>"
    modalId = gui.launchModal(modalTitle, content,
      actionButton: "<button type=\"button\" class=\"btn btn-danger button-accept\">" + gettext("Delete") + "</button>"
    )

    # Will show results once
    msgs = []
    count = values.length
    deletedFnc = (name, errorMsg) ->
      count -= 1
      if errorMsg?
        msgs.push gettext("Error deleting") + " <b>" + name + '</b>: <span class="text-danger">' + errorMsg + '</span>'
      else
        msgs.push gettext("Successfully deleted") + " <b>" + name + "</b>"

      if count == 0
        gui.tools.unblockUI()
        refreshFnc()
        gui.launchModal gettext('Deletion results'), '<ul><li>' + msgs.join('</li><li>') + '</li></ul>',
          actionButton: " "
          closeButton: '<button type="button" class="btn btn-default" data-dismiss="modal">Ok</button>'



    $(modalId + " .button-accept").click ->
      $(modalId).modal "hide"
      gui.tools.blockUI()
      for value in values
        ((value) ->
          name = value.name or value.friendly_name
          parent.rest.del value.id, (->
            deletedFnc name
            return
          ), (jqXHR, textStatus, errorThrown) -> # fail on delete
            deletedFnc(name, jqXHR.responseText))(value)
      return

    return
