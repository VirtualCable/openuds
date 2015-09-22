# jshint strict: true 
((gui, $, undefined_) ->
  "use strict"

  # Public attributes
  gui.debug = on
  
  # "public" methods
  gui.doLog = (args...)->
    if gui.debug
      try
        console.log args
      
    return

  
  # nothing can be logged
  gui.config = gui.config or {}
  
  # Several convenience "constants" for tables
  gui.config.dataTablesLanguage =
    sLengthMenu: gettext("_MENU_ records per page")
    sZeroRecords: gettext("Empty")
    sInfo: gettext("Records _START_ to _END_ of _TOTAL_")
    sInfoEmpty: gettext("No records")
    sInfoFiltered: gettext("(filtered from _MAX_ total records)")
    sProcessing: gettext("Please wait, processing")
    sSearch: gettext("Filter")
    sInfoThousands: django.formats.THOUSAND_SEPARATOR
    oPaginate:
      sFirst: "<span class=\"fa fa-fast-backward \"></span> "
      sLast: "<span class=\"fa fa-fast-forward\"></span> "
      sNext: "<span class=\"fa fa-forward\"></span> "
      sPrevious: "<span class=\"fa fa-backward\"></span> "
    select:
      rows:
        _: gettext("Selected %d rows")
        0: gettext("Click on a row to select it")
        1: gettext("Selected one row")


  gui.config.dataTableButtons =
    new:
      text: "<span class=\"fa fa-pencil\"></span> <span class=\"label-tbl-button\">" + gettext("New") + "</span>"
      css: "btn btn-primary btn-tables"

    edit:
      text: "<span class=\"fa fa-edit\"></span> <span class=\"label-tbl-button\">" + gettext("Edit") + "</span>"
      css: "btn disabled btn-default btn-tables"

    delete:
      text: "<span class=\"fa fa-trash-o\"></span> <span class=\"label-tbl-button\">" + gettext("Delete") + "</span>"
      css: "btn disabled btn-default btn-tables"

    permissions:
      text: "<span class=\"fa fa-save\"></span> <span class=\"label-tbl-button\">" + gettext("Permissions") + "</span>"
      css: "btn disabled btn-default btn-tables"

    xls:
      text: "<span class=\"fa fa-save\"></span> <span class=\"label-tbl-button\">" + gettext("Xls") + "</span>"
      css: "btn btn-info btn-tables"

    custom:
      text: null
      css: "btn btn-default btn3d-tables"

  gui.genRamdonId = (prefix) ->
    prefix = prefix or ""
    prefix + Math.random().toString().split(".")[1]

  gui.table = (title, table_id, options) ->
    options = options or {}
    panelId = "panel-" + table_id
    text: api.templates.evaluate("tmpl_comp_table",
      panelId: panelId
      icon: api.config.img_url + 'icons/' + (options.icon or 'maleta') + '.png'
      size: options.size or 12
      title: title
      table_id: table_id
    )
    panelId: panelId
    refreshSelector: "#" + panelId + " span.fa-refresh"

  gui.breadcrumbs = (path) ->
    items = path.split("/")
    active = items.pop()
    list = ""
    $.each items, (index, value) ->
      list += "<li><a href=\"#\">" + value + "</a></li>"
      return

    list += "<li class=\"active\">" + active + "</li>"
    "<div class=\"row\"><div class=\"col-lg-12\"><ol class=\"breadcrumb\">" + list + "</ol></div></div>"

  
  # By default, actionButton has class "button-accept", so you can use returned id + this class to select it
  # and do whatever is needed (for example, insert an "on click" event (this method returns id without '#'
  # Example: $('#' + id + ' .button-accept').on('click', ...
  gui.modal = (id, title, content, options) ->
    options = options or {}
    api.templates.evaluate "tmpl_comp_modal",
      id: id
      title: title
      content: content
      footer: options.footer
      button1: options.closeButton
      button2: options.actionButton
  
  # As previous, this creates the modal and shows it. in this case, the id of the modal returned already has '#'
  gui.launchModal = (title, content, options) ->
    options = options or {}
    id = gui.genRamdonId("modal-") # Get a random ID for this modal
    gui.appendToWorkspace gui.modal(id, title, content, options)
    id = "#" + id # for jQuery
    $(id).modal().on "hidden.bs.modal", ->
      $(id).remove()
      return

    id

  gui.notify = (message, type) ->
    gui.launchModal "<b class=\"text-" + type + "\">" + gettext("Message") + "</b>", "<span class=\"text-" + type + "\">" + message + "</span>",
      actionButton: " "
      closeButton: '<button type="button" class="btn btn-default" data-dismiss="modal">Ok</button>'

    return

  gui.failRequestModalFnc = (title) ->
    (jqXHR, textStatus, errorThrown) -> # fail on put
      gui.tools.unblockUI()
      gui.launchModal "<b class=\"text-danger\">" + title + "</b>", jqXHR.responseText,
        actionButton: " "

      return

  gui.promptModal = (title, question, options) ->
    options = options or {}
    options.actionButton = "<button type=\"button\" class=\"btn btn-primary button-yes\">" + (options.yesButton or gettext("yes")) + "</button>"
    options.closeButton = "<button type=\"button\" class=\"btn btn-danger button-no\">" + (options.yesButton or gettext("no")) + "</button>"
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

  gui.clearWorkspace = ->
    $("#content").empty()
    $("#minimized").empty()
    return

  gui.appendToWorkspace = (data) ->
    $(data).appendTo "#content"
    return

  
  # Clean up several "internal" data
  # I have discovered some "items" that are keep in memory, or that adds garbage to body (datatable && tabletools mainly)
  # Whenever we change "section", we clean up as much as we can, so we can keep things as clean as possible
  # Main problem where comming with "tabletools" and keeping references to all instances created
  gui.cleanup = ->
    gui.doLog "Cleaning up things"
    
    # Destroy any created datatable
    $.each $.fn.dataTable.fnTables(), (undefined_, tbl) ->
      $tbl = $(tbl).dataTable()
      $tbl.fnClearTable() # Removing data first makes things much faster
      $tbl.fnDestroy()
      return

    return

  gui.setLinksEvents = ->
    sidebarLinks = [
      {
        id: "lnk-dashboard"
        exec: gui.dashboard.link
        cleanup: true
      }
      {
        id: "lnk-service_providers"
        exec: gui.providers.link
        cleanup: true
      }
      {
        id: "lnk-authenticators"
        exec: gui.authenticators.link
        cleanup: true
      }
      {
        id: "lnk-osmanagers"
        exec: gui.osmanagers.link
        cleanup: true
      }
      {
        id: "lnk-connectivity"
        exec: gui.connectivity.link
        cleanup: true
      }
      {
        id: "lnk-deployed_services"
        exec: gui.servicesPools.link
        cleanup: true
      }
      {
        id: "lnk-clear_cache"
        exec: gui.clear_cache.link
        cleanup: false
      }
      {
        id: "lnk-configuration"
        exec: gui.configuration.link
        cleanup: false
      }
      {
        id: "lnk-gallery"
        exec: gui.gallery.link
        cleanup: true
      }
      {
        id: "lnk-reports"
        exec: gui.reports.link
        cleanup: true
      }
      {
        id: "lnk-calendars"
        exec: gui.calendars.link
        cleanup: true
      }
    ]
    $.each sidebarLinks, (index, value) ->
      gui.doLog "Adding " + value.id
      $("." + value.id).unbind("click").click (event) ->
        event.preventDefault()
        $(".navbar-toggle").trigger "click"  unless $(".navbar-toggle").css("display") is "none"
        gui.cleanup()  if value.cleanup
        $("html, body").scrollTop 0
        value.exec event
        return

      return

    return

  gui.init = ->
    gui.doLog $
    # Load jquery validator strings
    $.extend $.validator.messages,
      required: gettext("This field is required.")
      remote: gettext("Please fix this field.")
      email: gettext("Please enter a valid email address.")
      url: gettext("Please enter a valid URL.")
      date: gettext("Please enter a valid date.")
      dateISO: gettext("Please enter a valid date (ISO).")
      number: gettext("Please enter a valid number.")
      digits: gettext("Please enter only digits.")
      creditcard: gettext("Please enter a valid credit card number.")
      equalTo: gettext("Please enter the same value again.")
      maxlength: $.validator.format(gettext("Please enter no more than {0} characters."))
      minlength: $.validator.format(gettext("Please enter at least {0} characters."))
      rangelength: $.validator.format(gettext("Please enter a value between {0} and {1} characters long."))
      range: $.validator.format(gettext("Please enter a value between {0} and {1}."))
      max: $.validator.format(gettext("Please enter a value less than or equal to {0}."))
      min: $.validator.format(gettext("Please enter a value greater than or equal to {0}."))

    
    # Set blockui params
    $.blockUI.defaults.baseZ = 2000
    $.fn.dataTableExt.oSort["uds-date-pre"] = (s) ->
      parseInt s.split("\"")[1], 10

    
    # Sort for "date" columns (our "dates" are in fact postfix dates rendered as dates with locale format
    $.fn.dataTableExt.oSort["uds-date-asc"] = (x, y) ->
      val = ((if (x < y) then -1 else ((if (x > y) then 1 else 0))))
      val

    $.fn.dataTableExt.oSort["uds-date-desc"] = (x, y) ->
      val = ((if (x < y) then 1 else ((if (x > y) then -1 else 0))))
      val

    
    # Wait a bit before activating links to give tome tine to initializations
    setTimeout (->
      gui.setLinksEvents()
      gui.dashboard.link()
      return
    ), 500
    return

  gui.showDashboard = ->
    gui.dashboard.link()
    return

  
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
    (value, event, table, refreshFnc) ->
      gui.doLog value
      name = value.name or value.friendly_name
      content = gettext("Are you sure do you want to delete ") + "<b>" + name + "</b>"
      modalId = gui.launchModal(modalTitle, content,
        actionButton: "<button type=\"button\" class=\"btn btn-danger button-accept\">" + gettext("Delete") + "</button>"
      )
      $(modalId + " .button-accept").click ->
        $(modalId).modal "hide"
        parent.rest.del value.id, (->
          refreshFnc()
          gui.notify gettext("Sucess"), "success"
          return
        ), gui.failRequestModalFnc(modalErrorMsg)
        return

      return

  return
) window.gui = window.gui or {}, jQuery