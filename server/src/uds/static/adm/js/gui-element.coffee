# jshint strict: true

# Operations commmon to most elements
@BasicGuiElement = (name) ->
  "use strict"
  @name = name
  return
@GuiElement = (restItem, name, typesFunction) ->
  "use strict"
  @rest = restItem
  @name = name
  @types = {}
  @initialized = false
  @init()
  return

# all gui elements has, at least, name && type
# Types must include, at least: type, icon
@GuiElement:: =
  init: ->
    "use strict"
    gui.doLog "Initializing " + @name
    self = this
    @rest.types (data) ->
      styles = ""
      alreadyAttached = $("#gui-style-" + self.name).length isnt 0
      self.types = {}
      $.each data, (index, value) ->
        className = self.name + "-" + value.type
        self.types[value.type] = value
        self.types[value.type].css = className
        gui.doLog "Creating style for " + className
        unless alreadyAttached
          style = "." + className + " { display:inline-block; background: url(data:image/png;base64," + value.icon + "); background-size: 16px 16px; background-repeat: no-repeat; width: 16px; height: 16px; vertical-align: middle; } "
          styles += style
        return

      if styles isnt ""

        # If style already attached, do not re-attach it
        styles = "<style id=\"gui-style-" + self.name + "\" media=\"screen\">" + styles + "</style>"
        $(styles).appendTo "head"

      # Initialization finished
      self.initialized = true

      return

    return


  # Options: dictionary
  #   container: container ID of parent for the table. If undefined, table will be appended to workspace
  #   buttons: array of visible buttons (strings), valid are [ 'new', 'edit', 'refresh', 'delete', 'xls' ],
  #            Can contain also objects with {'text': ..., 'fnc': ...}
  #   rowSelect: type of allowed row selection, valid values are 'single' and 'multi'
  #   scrollToTable: if True, will scroll page to show table
  #   deferedRender: if True, datatable will be created with "bDeferRender": true, that will improve a lot creation of huge tables
  #
  #   onData: Event (function). If defined, will be invoked on data load (to allow preprocess of data)
  #   onLoad: Event (function). If defined, will be invoked when table is fully loaded.
  #           Receives 1 parameter, that is the gui element (GuiElement) used to render table
  #   onRowSelect: Event (function). If defined, will be invoked when a row of table is selected
  #                Receives 3 parameters:
  #                   1.- the array of selected items data (objects, as got from api...get)
  #                   2.- the DataTable that raised the event
  #                   3.- the DataTableTools that raised the event
  #   onRowDeselect: Event (function). If defined, will be invoked when a row of table is deselected
  #                Receives 3 parameters:
  #                   1.- the array of selected items data (objects, as got from api...get)
  #                   2.- the DataTable that raised the event
  #   onCheck:    Event (function),
  #               It determines the state of buttons on selection: if returns "true", the indicated button will be enabled, and disabled if returns "false"
  #               Receives 2 parameters:
  #                   1.- the event fired, that can be "edit" or "delete"
  #                   2.- the selected items data (array of selected elements, as got from api...get. In case of edit, array length will be 1)
  #   onNew: Event (function). If defined, will be invoked when "new" button is pressed
  #                Receives 4 parameters:
  #                   1.- the selected item data (single object, as got from api...get)
  #                   2.- the event that fired this (new, delete, edit, ..)
  #                   3.- the DataTable that raised the event
  #   onEdit: Event (function). If defined, will be invoked when "edit" button is pressed
  #                Receives 4 parameters:
  #                   1.- the selected item data (single object, as got from api...get)
  #                   2.- the event that fired this (new, delete, edit, ..)
  #                   3.- the DataTable that raised the event
  #   onDelete: Event (function). If defined, will be invoked when "delete" button is pressed
  #                Receives 4 parameters:
  #                   1.- the selected item data (single object, as got from api...get)
  #                   2.- the event that fired this (new, delete, edit, ..)
  #                   4.- the DataTable that raised the event
  #   onRefesh: ...
  #
  table: (tblParams) ->
    "use strict"

    tblParams = tblParams or {}
    self = this # Store this for child functions

    if self.initialized is false
      setTimeout (->
        gui.doLog 'Delaying table creation'
        self.table(tblParams)
        return
      ), 100
      return


    gui.doLog "Composing table for " + @name, tblParams
    tableId = @name + "-table"

    # ---------------
    # Cells renderers
    # ---------------

    # Empty cells transform
    renderEmptyCell = (data) ->
      return "-"  if data is ""
      data


    # Icon renderer, based on type (created on init methods in styles)
    renderTypeIcon = (data, type, value) ->
      if type is "display"
        self.types[value.type] = self.types[value.type] or {}
        css = self.types[value.type].css or "fa fa-asterisk"
        "<span class=\"" + css + "\"></span> " + renderEmptyCell(data)
      else
        renderEmptyCell data


    renderImage = (data) ->
      "<img src=\"data:image/png;base64," + data + "\">"

    # Custom icon renderer, in fact span with defined class
    renderIcon = (icon) ->
      (data, type, full) ->
        if type is "display"
          "<span class=\"" + icon + "\"></span> " + renderEmptyCell(data)
        else
          renderEmptyCell data

    # Custom icon based on type
    renderIconDict = (iconDict) ->
      (data, type, value) ->
        if type is "display"
          "<span class=\"" + iconDict[value.type] + "\"></span> " + renderEmptyCell(data)
        else
          renderEmptyCell data


    # Text transformation, dictionary based
    renderTextTransform = (dict) ->
      (data, type, full) ->
        dict[data] or renderEmptyCell(data)

    renderCallBack = (fld) ->
      gui.doLog "Rendering " + fld
      if tblParams.callback?
        callBack = tblParams.callback
        (data, type, value) ->
          callBack(fld, data, type, value)
      else
        (data) ->
          fld

    @rest.tableInfo (data) -> # Gets tableinfo data (columns, title, visibility of fields, etc...
      row_style = data["row-style"]
      title = data.title
      columns = [ {
            orderable: false,
            className: 'select-checkbox'
            width: "32px"
            render: () -> return ''
        } ]

      $.each data.fields, (index, value) ->
        for v of value
          opts = value[v]
          column = data: v
          column.title = opts.title
          column.render = renderEmptyCell
          column.width = opts.width  if opts.width?
          # column.width = "100px"
          column.visible = (if not opts.visible? then true else opts.visible)
          column.orderable = opts.sortable  if opts.sortable?
          column.searchable = opts.searchable  if opts.searchable?
          if opts.type and column.visible
            switch opts.type
              when "date"
                column.type = "uds-date"
                column.render = gui.tools.renderDate(api.tools.djangoFormat(get_format("SHORT_DATE_FORMAT")))
              when "datetime"
                column.type = "uds-date"
                column.render = gui.tools.renderDate(api.tools.djangoFormat(get_format("SHORT_DATETIME_FORMAT")))
              when "time"
                column.type = "uds-date"
                column.render = gui.tools.renderDate(api.tools.djangoFormat(get_format("TIME_FORMAT")))
              when "iconType"
                #columnt.type = 'html'; // html is default, so this is not needed
                column.render = renderTypeIcon
              when "icon"
                column.render = renderIcon(opts.icon)  if opts.icon?
              when "icon_dict"
                column.render = renderIconDict(opts.icon_dict)  if opts.icon_dict?
              when "image"
                column.render = renderImage
              when "dict"
                column.render = renderTextTransform(opts.dict)  if opts.dict?
              when "callback"
                column.render = renderCallBack(v)
              when "number"
                column.render = $.fn.dataTable.render.number(get_format("THOUSAND_SEPARATOR"), get_format("DECIMAL_SEPARATOR"))
              else
                column.type = opts.type
          columns.push column
        return

      lookupUuid = (dTable) ->
        if gui.lookupUuid?
          gui.doLog "Looking up #{gui.lookupUuid}"
          dTable.rows().every( (rowIdx, tableLoop, rowLoop) ->
              # rowLoop holds the position in sorted table
              try
                if this.data().id == gui.lookupUuid
                  gui.doLog "Found: #{this.data()}"
                  gui.lookupUuid = null
                  page = Math.floor(rowLoop / dTable.page.info().length)
                  dTable.page(page).draw(false)
                  this.select()
                  if tblParams.onFoundUuid?
                    tblParams.onFoundUuid(this)
              catch error
                ;
            )

      # Responsive style for tables, using tables.css and this code generates the "titles" for vertical display on small sizes
      initTable = (data) ->
        tblParams.onData data  if tblParams.onData
        table = gui.table(title, tableId,
          icon: tblParams.icon
        )
        if not tblParams.container?
          gui.appendToWorkspace "<div class=\"row\"><div class=\"col-lg-12\">" + table.text + "</div></div>"
        else
          $("#" + tblParams.container).empty()
          $("#" + tblParams.container).append table.text

        # What execute on refresh button push
        if not tblParams.onRefresh?
          tblParams.onRefresh = (tbl) ->
            return

         self.refresh = refreshFnc = () ->
            # Refreshes table content
            tbl = $("#" + tableId).DataTable()

            #if( data.length > 1000 )
            gui.tools.blockUI()
            setTimeout (->
              self.rest.overview( ((data) -> # Restore overview
                tblParams.onData data  if tblParams.onData
                tbl.rows().remove()
                if data.length > 0  # Only adds data if data is available
                  tbl.rows.add(data)

                tbl.columns.adjust().draw()
                selCallback null, tbl, null, null
                gui.doLog "onRefresh", tblParams.onRefresh
                tblParams.onRefresh self
                lookupUuid(tbl)
                gui.tools.unblockUI()), gui.failRequestModalFnc(gettext("Refresh operation failed"))
              )
              return
              ), 0
            return

        btns = []
        if tblParams.buttons
          # Generic click handler generator for this table
          clickHandlerFor = (handler, action, newHandler) ->
            gui.doLog "Setting click handler for ", handler, action, newHandler

            handleFnc = handler or (sel, action, dtable, refreshFnc) ->
              gui.doLog "Default handler called for ", sel, action
              return

            fnc = (btn, sel, dtable) ->
              gui.doLog "click handler: ", action, btn, sel, dtable
              setTimeout (->
                if newHandler
                  handleFnc action, dtable, refreshFnc
                else
                  handleFnc sel, action, dtable, refreshFnc
                return
              ), 0
              return

          onCheck = tblParams.onCheck or -> # Default oncheck always returns true
            true

          setBtnState = (btn, enable, cls) ->
            if enable
              $(btn).prop('disabled', false)
              $(btn).addClass('disabled')
              $(btn).removeClass("disabled") # .addClass cls
            else
              $(btn).prop('disabled', true)
              $(btn).removeClass(cls).addClass "disabled"
            return

          activeOnOneSelected = (cls) ->
            (btn, sel, dtable) ->
              setBtnState btn, (if sel.length is 1 then onCheck("edit", sel) else false), cls

          activeOnManySelected = (cls) ->
            (btn, sel, dtable) ->
              setBtnState btn, (if sel.length >= 1 then onCheck("delete", sel) else false), cls

          # methods for buttons on row select
          editSelected = activeOnOneSelected('btn-success')
          deleteSelected = activeOnManySelected('btn-danger')
          permissionsSelected = activeOnOneSelected('btn-success')

          $.each tblParams.buttons, (index, value) -> # Iterate through button definition
            btn = null
            switch value

              when "new", "new_grouped"
                grouped = if value is "new_grouped" then true else false
                if self.rest.permission() >= api.permissions.MANAGEMENT
                  if not api.tools.isEmpty(self.types)
                    menuId = gui.genRamdonId("dd-")
                    ordered = []
                    $.each self.types, (k, v) ->
                      val =
                        type: k
                        css: v.css
                        name: v.name
                        description: v.description
                        group: if v.group? then v.group else null

                      ordered.push val

                      return

                    ordered = ordered.sort((a, b) ->
                      a.name.localeCompare b.name
                    )

                    groups = []
                    if grouped
                      tmpGrp = {}
                      for val in ordered
                        if not tmpGrp[val.group]?
                          tmpGrp[val.group] = []
                        tmpGrp[val.group].push val

                      for k, v of tmpGrp
                        groups.push
                          name: k
                          values: v

                      gui.doLog "***********GROUPSSS", groups

                    btn =
                      type: "div"
                      content: api.templates.evaluate(
                        if not grouped then "tmpl_comp_dropdown" else "tmpl_comp_dropdown_grouped",
                        label: gui.config.dataTableButtons["new"].text
                        css: gui.config.dataTableButtons["new"].css
                        id: menuId
                        tableId: tableId
                        columns: columns
                        menu: if not grouped then ordered else groups
                      )
                  else
                    btn =
                      type: "text"
                      content: gui.config.dataTableButtons["new"].text
                      css: gui.config.dataTableButtons["new"].css
                      fnClick: () ->
                        selecteds = dTable.rows({selected: true}).data()
                        gui.doLog "New click: ", selecteds, dTable, refreshFnc
                        tblParams.onNew "new", dTable, refreshFnc
              when "edit"
                if self.rest.permission() >= api.permissions.MANAGEMENT
                  btn =
                    type: "text"
                    content: gui.config.dataTableButtons.edit.text
                    fnSelect: editSelected
                    fnClick: () ->
                      selecteds = dTable.rows({selected: true}).data()
                      gui.doLog "Edit click: ", selecteds, dTable, refreshFnc
                      tblParams.onEdit selecteds[0], "edit", dTable, refreshFnc
                    css: gui.config.dataTableButtons.edit.css
              when "delete"
                if self.rest.permission() >= api.permissions.MANAGEMENT
                  btn =
                    type: "text"
                    content: gui.config.dataTableButtons["delete"].text
                    fnSelect: deleteSelected
                    css: gui.config.dataTableButtons["delete"].css
                    fnClick: () ->
                      selecteds = dTable.rows({selected: true}).data()
                      gui.doLog "delete click: ", selecteds, dTable, refreshFnc
                      tblParams.onDelete selecteds, "delete", dTable, refreshFnc
              when "refresh"
                btn =
                  type: "text"
                  content: gui.config.dataTableButtons.refresh.text
                  fnClick: refreshFnc
                  css: gui.config.dataTableButtons.refresh.css
              when "permissions"
                if self.rest.permission() == api.permissions.ALL
                  btn =
                    type: "text"
                    content: gui.config.dataTableButtons.permissions.text
                    fnSelect: permissionsSelected
                    fnClick: () ->
                      selecteds = dTable.rows({selected: true}).data()
                      gui.doLog "Permissions click: ", selecteds, dTable, refreshFnc
                      gui.permissions selecteds[0], self.rest, dTable, refreshFnc

                    css: gui.config.dataTableButtons.permissions.css
              when "xls"
                btn =
                  type: "text"
                  content: gui.config.dataTableButtons.xls.text
                  fnClick: -> # Export to excel
                    api.spreadsheet.tableToExcel(tableId, title)
                    return
                  # End export to excell
                  css: gui.config.dataTableButtons.xls.css
              else # Custom button, this has to be
                perm = if value.permission? then value.permission else api.permissions.NONE
                if self.rest.permission() >= perm
                  try
                    css = ((if value.css then value.css + " " else "")) + gui.config.dataTableButtons.custom.css
                    btn =
                      type: "text"
                      content: value.text
                      css: css
                      disabled: value.disabled? and value.disabled is true

                    if value.click
                      btn.fnClick = () ->
                        selecteds = dTable.rows({selected: true}).data()
                        setTimeout (->
                          value.click selecteds, value, this, dTable, refreshFnc
                          return
                        ), 0
                        return
                    if value.select
                      btn.fnSelect = (btn, selecteds, dtable) ->
                        setTimeout (->
                          value.select selecteds, value, btn, dTable, refreshFnc
                          return
                        ), 0
                        return
                  catch e
                    gui.doLog "Button", value, e
            btns.push btn  if btn
            return

        # End buttoon iteration

        tbId = gui.genRamdonId('tb')
        dataTableOptions =
          responsive: false
          colReorder: true
          stateSave: true
          paging: true
          info: true
          autoWidth: true
          lengthChange: false
          pageLength: 10

          ordering: true
          order: [[ 1, 'asc' ]]

          dom: '<"' + tbId + ' btns-tables">fr<"uds-table"t>ip'

          select:
            style: if tblParams.rowSelect == 'multi' then 'os' else 'single'
            #selector: 'td:first-child'

          columns: columns
          data: data
          deferRender: tblParams.deferedRender or tblParams.deferRender or false

          language: gui.config.dataTablesLanguage


        # If row is "styled"
        if row_style.field
          field = row_style.field
          dct = row_style.dict
          prefix = row_style.prefix
          dataTableOptions.createdRow = (row, data, dataIndex) ->
            # gui.doLog row, data, dataIndex, data[field]
            try
              v = (if dct? then dct[data[field]] else data[field])
              $(row).addClass prefix + v
            catch err
              gui.doLog "Exception got: ", err

            return

        dTable = $("#" + tableId).DataTable dataTableOptions

        # dTable = $("#" + tableId).dataTable()

        if tblParams.onRowSelect
          rowSelectedFnc = tblParams.onRowSelect
          dTable.on 'select', (e, dt, type, indexes) ->
            rows = dt.rows({selected: true}).data()
            # rows = dt.rows(indexes).data()  # This gets selected rows on call
            rowSelectedFnc rows, dt
            return
            #rowSelectedFnc @fnGetSelectedData(), $("#" + tableId).dataTable(), self

        if tblParams.onRowDeselect
          rowDeselectedFnc = tblParams.onRowDeselect
          dTable.on 'deselect', (e, dt, type, indexes) ->
            rows = dt.rows(indexes).data()
            gui.doLog "Deselect: ", dt.rows({selected: true}).length, dt.rows({selected: true}).data().length
            rowDeselectedFnc rows, dt
            return

        # For storing on select callbacks
        selCallbackList = []
        # Add buttons
        for btn in btns
          $div = $('div.'+tbId)
          if btn.type == 'text'
            gui.doLog "Button: ", btn

            btnId = gui.genRamdonId('btn')
            btnHtml = '<button id="' + btnId + '" class="' + btn.css + '"'
            if btn.disabled? and btn.disabled is true
              btnHtml += ' disabled'
            btnHtml += '>' + btn.content + '</button>'

            gui.doLog "Button2: ", btnHtml

            $div.append btnHtml
            $btn = $('#'+btnId)
            $btn.on 'click', btn.fnClick

            if btn.fnSelect?
              selCallbackList.push
                btnId: '#' + btnId
                callback: btn.fnSelect
              btn.fnSelect $btn, [], dTable
          else
            $div.append('<div style="float: left;">' + btn.content + '</div>')

        # Listener for callbacks
        selCallback = (e, dt, type, indexes) ->
          for v in selCallbackList
            rows = dt.rows({selected: true}).data()
            v.callback($(v.btnId), rows, dt)

        dTable.on 'select', selCallback
        dTable.on 'deselect', selCallback

        # Fix filter
        $("#" + tableId + "_filter label").addClass "form-inline"
        $("#" + tableId + "_filter input").addClass "form-control"

        # Add refresh action to panel
        $(table.refreshSelector).click refreshFnc

        # Add tooltips to "new" buttons
        $("#" + table.panelId + " [data-toggle=\"tooltip\"]").tooltip
          container: "body"
          delay:
            show: 1000
            hide: 100

          placement: "auto right"


        # And the handler of the new "dropdown" button links
        if tblParams.onNew # If onNew, set the handlers for dropdown
          $("#" + table.panelId + " [data-type]").on "click", (event) ->
            event.preventDefault()
            tbl = $("#" + tableId).dataTable()

            # Executes "onNew" outside click event
            type = $(this).attr("data-type")
            setTimeout (->
              tblParams.onNew type, tbl, refreshFnc
              return
            ), 0
            return

        if tblParams.scrollToTable is true
          tableTop = $("#" + tableId).offset().top
          $("html, body").scrollTop tableTop

        gui.test = dTable
        # Try to locate gui.lookupUuid as last action
        lookupUuid(dTable)

        # if table rendered event
        tblParams.onLoad self  if tblParams.onLoad
        return

      if tblParams.doNotLoadData isnt true
        self.rest.overview (data) -> # Gets "overview" data for table (table contents, but resume form)
          initTable(data)
      else
        initTable([])

      return

    # End Overview data
    # End Tableinfo data
    "#" + tableId

  logTable: (itemId, tblParams) ->
    "use strict"
    tblParams = tblParams or {}
    gui.doLog "Composing log for " + @name
    tableId = @name + "-table-log"
    self = this # Store this for child functions

    # Renderers for columns
    refreshFnc = ->
      # Refreshes table content
      tbl = $("#" + tableId).dataTable()
      gui.tools.blockUI()
      self.rest.getLogs itemId, (data) ->
        setTimeout (->
          tbl.fnClearTable()
          if data.length > 0
            tbl.fnAddData data
          gui.tools.unblockUI()
          return
        ), 0
        return

      # End restore overview
      false # This may be used on button or href, better disable execution of it


    # Log level "translator" (renderer)
    logRenderer = gui.tools.renderLogLovel()

    # Columns description
    columns = [
      {
        data: "date"
        title: gettext("Date")
        type: "uds-date"
        asSorting: [
          "desc"
          "asc"
        ]
        render: gui.tools.renderDate(api.tools.djangoFormat(get_format("SHORT_DATE_FORMAT") + " " + get_format("TIME_FORMAT")))
        orderable: true
        searchable: true
      }
      {
        data: "level"
        title: gettext("level")
        render: logRenderer
        width: "5em"
        orderable: true
        searchable: true
      }
      {
        data: "source"
        title: gettext("source")
        width: "5em"
        orderable: true
        searchable: true
      }
      {
        data: "message"
        title: gettext("message")
        orderable: true
        searchable: true
      }
    ]
    table = gui.table(tblParams.title or gettext("Logs"), tableId,
      icon: tblParams.icon or 'logs'
    )
    if not tblParams.container?
      gui.appendToWorkspace "<div class=\"row\"><div class=\"col-lg-12\">" + table.text + "</div></div>"
    else
      $("#" + tblParams.container).empty()
      $("#" + tblParams.container).append table.text

    # Responsive style for tables, using tables.css and this code generates the "titles" for vertical display on small sizes
    tbId = gui.genRamdonId('tb')
    initLog = (data) ->
      $("#" + tableId).DataTable
        data: data
        ordering: true
        order: [[ 1, 'desc' ]]

        columns: columns
        language: gui.config.dataTablesLanguage
        # dom: '<"' + tbId + ' btns-tables">fr<"uds-table"t>ip'
        dom: '<"' + tbId + ' btns-tables">fr<"uds-table"t>ip'

        # dom: "<'row'<'col-xs-8'T><'col-xs-4'f>r>t<'row'<'col-xs-5'i><'col-xs-7'p>>"
        deferRender: tblParams.deferedRender or tblParams.deferRender or false
        # bDeferRender: tblParams.deferedRender or false
        createdRow: (row, data, dataIndex) ->
          try
            v = "log-" + logRenderer(data.level)
            $(row).addClass v
          catch error
            gui.doLog "Log cretedRow error", error

          return


      # Fix form
      $("#" + tableId + "_filter label").addClass "form-inline"
      $("#" + tableId + "_filter input").addClass "form-control"

      # Add refresh action to panel
      $(table.refreshSelector).click refreshFnc

      # if table rendered event
      tblParams.onLoad self  if tblParams.onLoad
      return

    if tblParams.doNotLoadData isnt true
      self.rest.getLogs itemId, (data) -> # Gets "overview" data for table (table contents, but resume form)
        initLog(data)
    else
      initLog([])


    return "#" + tableId
