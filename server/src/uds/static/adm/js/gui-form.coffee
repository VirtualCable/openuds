# jshint strict: true 
((gui, $, undefined_) ->
  "use strict"
  gui.forms = {}
  gui.forms.callback = (formSelector, method, params, success_fnc) ->
    path = "gui/callback/" + method
    p = []
    $.each params, (index, val) ->
      p.push val.name + "=" + encodeURIComponent(val.value)
      return

    path = path + "?" + p.join("&")
    api.getJson path,
      success: success_fnc

    return

  
  # Returns form fields that will manage a gui description (new or edit)
  gui.forms.fieldsToHtml = (itemGui, item, editing) ->
    html = ""
    fillers = [] # Fillers (callbacks)
    originalValues = {} # Initial stored values (defaults to "reset" form and also used on fillers callback to try to restore previous value)
    # itemGui is expected to have fields sorted by .gui.order (REST api returns them sorted)
    index = 0
    $.each itemGui, (index, f) ->
      index = index + 1
      # Not exactly a field, maybe some other info...
      gui.doLog "Processing ", f
      return  if not f.gui?
      
      # Fix multiline text fields to textbox
      f.gui.type = "textbox" if f.gui.type is "text" and f.gui.multiline
      value = item[f.name]
      if !value?    # If a is null or undefined
        gui.doLog "Value is null"
        value =  f.gui.value or f.gui.defvalue
      
      # We need to convert "array" values for multichoices to single list of ids (much more usable right here)
      if f.gui.type is "multichoice"
        newValue = []
        $.each value, (undefined_, val) ->
          newValue.push val.id
          return
        value = newValue

      # Generate an unique id so templates can use it if needed
      id = "uniq" + Math.random().toString().split(".")[1]

      originalValues[f.name] = value # Store original value
      html += api.templates.evaluate("tmpl_fld_" + f.gui.type,
        index: index
        id: id
        value: value # If no value present, use default value
        minValue: f.gui.minValue
        maxValue: f.gui.maxValue
        values: f.gui.values
        label: f.gui.label
        length: f.gui.length
        multiline: f.gui.multiline
        readonly: (if editing is true then f.gui.rdonly else if editing is "readonly" then true else false) # rdonly applies just to editing
        required: f.gui.required
        tooltip: f.gui.tooltip
        type: f.gui.type
        name: f.name
        css: "modal_field_data"
      )

      # if this field has a filler (callback to get data)
      if f.gui.fills
        gui.doLog "This field has a filler"
        fillers.push
          name: f.name
          callbackName: f.gui.fills.callbackName
          parameters: f.gui.fills.parameters

      return

    html: html
    fillers: fillers
    originalValues: originalValues

  gui.forms.fromFields = (fields, item) ->
    editing = item? # Locate real Editing
    item = item or id: ""
    form = "<form class=\"form-horizontal\" role=\"form\">" + "<input type=\"hidden\" name=\"id\" class=\"modal_field_data\" value=\"" + item.id + "\">"
    fillers = []
    originalValues = {}
    if fields.tabs
      id = "tab-" + Math.random().toString().split(".")[1] # Get a random base ID for tab entries
      tabs = []
      tabsContent = []
      active = " active in"
      $.each fields.tabs, (index, tab) ->
        h = gui.forms.fieldsToHtml(tab.fields, item)
        tabsContent.push "<div class=\"tab-pane fade" + active + "\" id=\"" + id + index + "\">" + h.html + "</div>"
        tabs.push "<li><a href=\"#" + id + index + "\" data-toggle=\"tab\">" + tab.title + "</a></li>"
        active = ""
        fillers = fillers.concat(h.fillers) # Fillers (callback based)
        $.extend originalValues, h.originalValues # Original values
        gui.doLog "Fillers:", h.fillers
        return

      form += "<ul class=\"nav nav-tabs\">" + tabs.join("\n") + "</ul><div class=\"tab-content\">" + tabsContent.join("\n") + "</div>"
    else
      h = gui.forms.fieldsToHtml(fields, item, editing)
      form += h.html
      fillers = fillers.concat(h.fillers)
      $.extend originalValues, h.originalValues
    form += "</form>"
    gui.doLog "Original values: ", originalValues

    # Init function for callbacks.
    # Callbacks can only be attached to "Selects", but it's parameters can be got from any field
    # This needs the "form selector" as base for setting callbacks, etc..
    init = (formSelector) ->
      gui.doLog formSelector, fillers
      onChange = (filler) ->
        ->
          gui.doLog "Onchange invoked for ", filler
          
          # Attach on change method to each filler, and after that, all 
          params = []
          $.each filler.parameters, (undefined_, p) ->
            val = $(formSelector + " [name=\"" + p + "\"]").val()
            params.push
              name: p
              value: val

            return

          gui.forms.callback formSelector, filler.callbackName, params, (data) ->
            $.each data, (undefined_, sel) ->
              
              # Update select contents with returned values
              $select = $(formSelector + " [name=\"" + sel.name + "\"]")
              $select.empty()
              $.each sel.values, (undefined_, value) ->
                $select.append "<option value=\"" + value.id + "\">" + value.text + "</option>"
                return

              $select.val originalValues[sel.name]
              
              # Refresh selectpicker if item is such
              $select.selectpicker "refresh"  if $select.hasClass("selectpicker")
              
              # Trigger change for the changed item
              $select.trigger "change"
              return

            return

          return

      
      # Sets the "on change" event for select with fillers (callbacks that fills other fields)
      $.each fillers, (undefined_, f) ->
        $(formSelector + " [name=\"" + f.name + "\"]").on "change", onChange(f)
        return

      
      # Trigger first filler if it exists, this will cascade rest of "changes" if they exists
      $(formSelector + " [name=\"" + fillers[0].name + "\"]").trigger "change"  if fillers.length
      return

    html: form # Returns the form and a initialization function for the form, that must be invoked to start it
    init: init

  
  # Reads fields from a form
  gui.forms.read = (formSelector) ->
    res = {}
    $(formSelector + " .modal_field_data").each (i, field) ->
      $field = $(field)
      if $field.attr("name") # Is a valid field
        name = $field.attr("name")
        if $field.attr("type") is "checkbox"
          res[name] = $field.is(":checked")
        else if $field.attr("data-uds") is "list"
          res[name] = $field.val().split('/**/')
        else if $field.attr("data-uds") is "commaList"
          res[name] = $field.val().split(',')
        else
          res[name] = $field.val()
          res[name] = []  if not res[name]? and $field.is("select")
      return

    gui.doLog res
    res

  
  # Options has this keys:
  #   title
  #   fields
  #   item
  #   success
  #   buttons: Array of buttons to be added to footer, with:
  #            text --> text of button
  #            css  --> button style (btn-default, btn-warning, ...). If not defined, 'btn-default' will be used
  #            action --> function to be executed. Will be passed 3 parameters: event, formSelector and closeFnc
  #                       (use gui.forms.read(form selector) to get fields, closeFnc() to close form if desired)
  # Failed operations will show a modal with server error
  gui.forms.launchModal = (options, onSuccess) ->
    options = options or {}
    gui.doLog options
    id = "modal-" + api.tools.random() # Get a random ID for this modal
    ff = gui.forms.fromFields(options.fields, options.item)
    footer = ""
    clickEventHandlers = []
    if options.buttons
      $.each options.buttons, (index, value) ->
        _id = id + "-footer-" + index
        css = value.css or "btn-default"
        clickEventHandlers.push
          id: "#" + _id
          action: value.action

        footer += "<button id=\"" + _id + "\" type=\"button\" class=\"pull-left btn " + css + "\">" + value.text + "</button>"
        return

    gui.appendToWorkspace gui.modal(id, options.title, ff.html,
      footer: footer
      actionButton: options.actionButton
    )
    id = "#" + id # for jQuery
    formSelector = id + " form"
    closeFnc = ->
      $(id).modal "hide"
      return

    ff.init id  if ff.init
    
    # Append click events for custom buttons on footer
    $.each clickEventHandlers, (undefined_, value) ->
      if value.action?
        $(value.id).on "click", (event) ->
          value.action event, formSelector, closeFnc
          return

      return

    
    # Get form
    $form = $(id + " form")
    gui.tools.applyCustoms id
    
    # Validation


    $form.validate
      debug: true
      ignore: ':hidden:not("select")'
      errorClass: "text-danger"
      validClass: "has-success"
      highlight: (element) ->
        $(element).closest(".form-group").addClass "has-error"
        return

      success: (element) ->
        $(element).closest(".form-group").removeClass "has-error"
        $(element).remove()
        return

    # Generate rules for required select fields
    for s in $($form.selector + " select[multiple][required]")
      gui.doLog "Rules ", $(s).rules()
    
    
    # And catch "accept" (default is "Save" in fact) button click
    $("#{id} .button-accept").click ->
      return  unless $form.valid()
      if options.success
        options.success formSelector, closeFnc # Delegate close to to onSuccess
        return
      else
        closeFnc()
      return

    
    # If preprocessors of modal (maybe custom event handlers)
    options.preprocessor id  if options.preprocessor
    
    # Launch modal
    $(id).modal(keyboard: false).on "hidden.bs.modal", ->
      $(id).remove()
      return

    return

  gui.forms.confirmModal = (title, question, options) ->
    options = options or {}
    options.actionButton = "<button type=\"button\" class=\"btn btn-primary button-yes\">" + (options.yesButton or gettext("yes")) + "</button>"
    options.closeButton = "<button type=\"button\" class=\"btn btn-danger button-no\">" + (options.noButton or gettext("no")) + "</button>"
    onYes = options.onYes or ->

    onNo = options.onNo or ->

    modalId = gui.launchModal(title, question, options)
    $(modalId + " .button-yes").on "click", (event) ->
      $(modalId).modal "hide"
      onYes()
      return

    $(modalId + " .button-no").on "click", (event) ->
      $(modalId).modal "hide"
      onNo()
      return

    return

  gui.forms.promptModal = (title, message, options) ->
    options = options or {}
    options.actionButton = "<button type=\"button\" class=\"btn btn-primary button-yes\">" + (options.acceptButton or gettext("Accept")) + "</button>"
    options.closeButton = "<button type=\"button\" class=\"btn btn-danger button-no\">" + (options.closeButton or gettext("Close")) + "</button>"

    onAccept = options.onAccept or ->
    onClose = options.onClose or ->

    html = '<div class="row"><div class="col-sm-12">' + message + '</div></div><div class="row"><div class="col-sm-12"><input class="form-control" type="text" name="text" autofocus></div></div>'

    modalId = gui.launchModal(title, html, options)

    textField = $(modalId + ' input[name="text"]')
    setTimeout ()->
      textField.focus()
    , 100

    $(modalId + " .button-yes").on "click", (event) ->
      text = textField.val()
      $(modalId).modal "hide"
      onAccept(text)
      return

    $(modalId + " .button-no").on "click", (event) ->
      $(modalId).modal "hide"
      onClose()
      return
    gui.doLog "***** Datos ", modalId, textField

    return

  
  # simple gui generators
  gui.forms.guiField = (name, type, label, tooltip, value, values, length, multiline, readonly, required) ->
    length = length or 128
    multiline = multiline ? 0
    readonly = readonly or false
    required = required or false
    name: name
    gui:
      defvalue: value
      value: value
      values: values
      label: label
      length: length
      multiline: multiline
      rdonly: readonly # rdonly applies just to editing
      required: required
      tooltip: tooltip
      type: type

  return
) window.gui = window.gui or {}, jQuery