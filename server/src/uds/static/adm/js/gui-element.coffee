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
  table: (tblParams) ->
    "use strict"
    tblParams = tblParams or {}
    gui.doLog "Composing table for " + @name
    tableId = @name + "-table"
    self = this # Store this for child functions
    
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

    @rest.tableInfo (data) -> # Gets tableinfo data (columns, title, visibility of fields, etc...
      row_style = data["row-style"]
      gui.doLog row_style
      title = data.title
      columns = []
      $.each data.fields, (index, value) ->
        for v of value
          opts = value[v]
          column = mData: v
          column.sTitle = opts.title
          column.mRender = renderEmptyCell
          column.sWidth = opts.width  if opts.width
          column.bVisible = (if not opts.visible? then true else opts.visible)
          column.bSortable = opts.sortable  if opts.sortable?
          column.bSearchable = opts.searchable  if opts.searchable?
          if opts.type and column.bVisible
            switch opts.type
              when "date"
                column.sType = "uds-date"
                column.mRender = gui.tools.renderDate(api.tools.djangoFormat(get_format("SHORT_DATE_FORMAT")))
              when "datetime"
                column.sType = "uds-date"
                column.mRender = gui.tools.renderDate(api.tools.djangoFormat(get_format("SHORT_DATETIME_FORMAT")))
              when "time"
                column.sType = "uds-date"
                column.mRender = gui.tools.renderDate(api.tools.djangoFormat(get_format("TIME_FORMAT")))
              when "iconType"
                
                #columnt.sType = 'html'; // html is default, so this is not needed
                column.mRender = renderTypeIcon
              when "icon"
                column.mRender = renderIcon(opts.icon)  if opts.icon?
              when "icon_dict"
                column.mRender = renderIconDict(opts.icon_dict)  if opts.icon_dict?
              when "dict"
                column.mRender = renderTextTransform(opts.dict)  if opts.dict?
              else
                column.sType = opts.type
          columns.push column
        return

      
      # Responsive style for tables, using tables.css and this code generates the "titles" for vertical display on small sizes
      $("#style-" + tableId).remove() # Remove existing style for table before adding new one
      $(api.templates.evaluate("tmpl_comp_responsive_table",
        tableId: tableId
        columns: columns
      )).appendTo "head"
      self.rest.overview (data) -> # Gets "overview" data for table (table contents, but resume form)
        tblParams.onData data  if tblParams.onData
        table = gui.table(title, tableId)
        if not tblParams.container?
          gui.appendToWorkspace "<div class=\"row\"><div class=\"col-lg-12\">" + table.text + "</div></div>"
        else
          $("#" + tblParams.container).empty()
          $("#" + tblParams.container).append table.text
        
        # What execute on refresh button push
        onRefresh = tblParams.onRefresh or ->

        refreshFnc = ->
          # Refreshes table content
          tbl = $("#" + tableId).dataTable()
          
          # Clears selection first
          TableTools.fnGetInstance(tableId).fnSelectNone()
          
          #if( data.length > 1000 )
          gui.tools.blockUI()
          self.rest.overview (data) -> # Restore overview
            tblParams.onData data  if tblParams.onData
            setTimeout (->
              tbl.fnClearTable()
              if data.length > 0  # Only adds data if data is available
                tbl.fnAddData data
              onRefresh self
              gui.tools.unblockUI()
              return
            ), 0
            return

          # End restore overview
          false # This may be used on button or href, better disable execution of it

        btns = []
        if tblParams.buttons
          
          # Generic click handler generator for this table
          clickHandlerFor = (handler, action, newHandler) ->
            handleFnc = handler or (val, action, tbl) ->
              gui.doLog "Default handler called for ", action
              return

            (btn) ->
              tbl = $("#" + tableId).dataTable()
              val = @fnGetSelectedData()[0]
              setTimeout (->
                if newHandler
                  handleFnc action, tbl, refreshFnc
                else
                  handleFnc val, action, tbl, refreshFnc
                return
              ), 0
              return

          onCheck = tblParams.onCheck or -> # Default oncheck always returns true
            true

          
          # methods for buttons on row select
          editSelected = (btn, obj, node) ->
            sel = @fnGetSelectedData()
            enable = (if sel.length is 1 then onCheck("edit", sel) else false)
            if enable
              $(btn).removeClass("disabled").addClass "btn3d-success"
            else
              $(btn).removeClass("btn3d-success").addClass "disabled"
            return

          deleteSelected = (btn, obj, node) ->
            sel = @fnGetSelectedData()
            enable = (if sel.length is 1 then onCheck("delete", sel) else false)
            if enable
              $(btn).removeClass("disabled").addClass "btn3d-warning"
            else
              $(btn).removeClass("btn3d-warning").addClass "disabled"
            return

          $.each tblParams.buttons, (index, value) -> # Iterate through button definition
            btn = null
            switch value
              when "new"
                if Object.keys(self.types).length isnt 0
                  menuId = gui.genRamdonId("dd-")
                  ordered = []
                  $.each self.types, (k, v) ->
                    ordered.push
                      type: k
                      css: v.css
                      name: v.name
                      description: v.description

                    return

                  ordered = ordered.sort((a, b) ->
                    a.name.localeCompare b.name
                  )
                  btn =
                    sExtends: "div"
                    sButtonText: api.templates.evaluate("tmpl_comp_dropdown",
                      label: gui.config.dataTableButtons["new"].text
                      css: gui.config.dataTableButtons["new"].css
                      id: menuId
                      tableId: tableId
                      columns: columns
                      menu: ordered
                    )
                else
                  btn =
                    sExtends: "text"
                    sButtonText: gui.config.dataTableButtons["new"].text
                    sButtonClass: gui.config.dataTableButtons["new"].css
                    fnClick: clickHandlerFor(tblParams.onNew, "new", true)
              when "edit"
                btn =
                  sExtends: "text"
                  sButtonText: gui.config.dataTableButtons.edit.text
                  fnSelect: editSelected
                  fnClick: clickHandlerFor(tblParams.onEdit, "edit")
                  sButtonClass: gui.config.dataTableButtons.edit.css
              when "delete"
                btn =
                  sExtends: "text"
                  sButtonText: gui.config.dataTableButtons["delete"].text
                  fnSelect: deleteSelected
                  fnClick: clickHandlerFor(tblParams.onDelete, "delete")
                  sButtonClass: gui.config.dataTableButtons["delete"].css
              when "refresh"
                btn =
                  sExtends: "text"
                  sButtonText: gui.config.dataTableButtons.refresh.text
                  fnClick: refreshFnc
                  sButtonClass: gui.config.dataTableButtons.refresh.css
              when "xls"
                btn =
                  sExtends: "text"
                  sButtonText: gui.config.dataTableButtons.xls.text
                  fnClick: -> # Export to excel
                    api.spreadsheet.tableToExcel(tableId, title)
                    return

                  # End export to excell
                  sButtonClass: gui.config.dataTableButtons.xls.css
              else # Custom button, this has to be
                try
                  css = ((if value.css then value.css + " " else "")) + gui.config.dataTableButtons.custom.css
                  btn =
                    sExtends: "text"
                    sButtonText: value.text
                    sButtonClass: css

                  if value.click
                    btn.fnClick = (btn) ->
                      tbl = $("#" + tableId).dataTable()
                      val = @fnGetSelectedData()[0]
                      setTimeout (->
                        value.click val, value, btn, tbl, refreshFnc
                        return
                      ), 0
                      return
                  if value.select
                    btn.fnSelect = (btn) ->
                      tbl = $("#" + tableId).dataTable()
                      val = @fnGetSelectedData()[0]
                      setTimeout (->
                        value.select val, value, btn, tbl, refreshFnc
                        return
                      ), 0
                      return
                catch e
                  gui.doLog "Button", value, e
            btns.push btn  if btn
            return

        # End buttoon iteration
        
        # Initializes oTableTools
        oTableTools =
          aButtons: btns
          sRowSelect: tblParams.rowSelect or "none"

        if tblParams.onRowSelect
          rowSelectedFnc = tblParams.onRowSelect
          oTableTools.fnRowSelected = ->
            rowSelectedFnc @fnGetSelectedData(), $("#" + tableId).dataTable(), self
            return
        if tblParams.onRowDeselect
          rowDeselectedFnc = tblParams.onRowDeselect
          oTableTools.fnRowDeselected = ->
            rowDeselectedFnc @fnGetSelectedData(), $("#" + tableId).dataTable(), self
            return
        dataTableOptions =
          aaData: data
          aaSorting: [[
            0
            "asc"
          ]]
          aoColumns: columns
          oLanguage: gui.config.dataTablesLanguage
          oTableTools: oTableTools
          sPaginationType: "bootstrap"
          
          # First is upper row,
          # second row is lower
          # (pagination) row
          sDom: "<'row'<'col-xs-8'T><'col-xs-4'f>r>t<'row'<'col-xs-5'i><'col-xs-7'p>>"
          bDeferRender: tblParams.deferedRender or false

        
        # If row is "styled"
        if row_style.field
          field = row_style.field
          dct = row_style.dict
          prefix = row_style.prefix
          dataTableOptions.fnCreatedRow = (nRow, aData, iDataIndex) ->
            v = (if dct? then dct[@fnGetData(iDataIndex)[field]] else @fnGetData(iDataIndex)[field])
            $(nRow).addClass prefix + v
            gui.doLog prefix + v
            return
        $("#" + tableId).dataTable dataTableOptions
        
        # Fix 3dbuttons
        gui.tools.fix3dButtons "#" + tableId + "_wrapper .btn-group-3d"
        
        # Fix form 
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
        
        # if table rendered event
        tblParams.onLoad self  if tblParams.onLoad
        return

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
        mData: "date"
        sTitle: gettext("Date")
        sType: "uds-date"
        asSorting: [
          "desc"
          "asc"
        ]
        mRender: gui.tools.renderDate(api.tools.djangoFormat(get_format("SHORT_DATE_FORMAT") + " " + get_format("TIME_FORMAT")))
        bSortable: true
        bSearchable: true
      }
      {
        mData: "level"
        sTitle: gettext("level")
        mRender: logRenderer
        sWidth: "5em"
        bSortable: true
        bSearchable: true
      }
      {
        mData: "source"
        sTitle: gettext("source")
        sWidth: "5em"
        bSortable: true
        bSearchable: true
      }
      {
        mData: "message"
        sTitle: gettext("message")
        bSortable: true
        bSearchable: true
      }
    ]
    table = gui.table(tblParams.title or gettext("Logs"), tableId)
    if not tblParams.container?
      gui.appendToWorkspace "<div class=\"row\"><div class=\"col-lg-12\">" + table.text + "</div></div>"
    else
      $("#" + tblParams.container).empty()
      $("#" + tblParams.container).append table.text
    
    # Responsive style for tables, using tables.css and this code generates the "titles" for vertical display on small sizes
    $("#style-" + tableId).remove() # Remove existing style for table before adding new one
    $(api.templates.evaluate("tmpl_comp_responsive_table",
      tableId: tableId
      columns: columns
    )).appendTo "head"
    self.rest.getLogs itemId, (data) ->
      gui.doLog data
      $("#" + tableId).dataTable
        aaData: data
        aaSorting: [[
          0
          "desc"
        ]]
        oTableTools:
          aButtons: []

        aoColumns: columns
        oLanguage: gui.config.dataTablesLanguage
        sDom: "<'row'<'col-xs-8'T><'col-xs-4'f>r>t<'row'<'col-xs-5'i><'col-xs-7'p>>"
        bDeferRender: tblParams.deferedRender or false
        fnCreatedRow: (nRow, aData, iDataIndex) ->
          v = "log-" + logRenderer(@fnGetData(iDataIndex).level)
          $(nRow).addClass v
          return

      
      # Fix form 
      $("#" + tableId + "_filter input").addClass "form-control"
      
      # Add refresh action to panel
      $(table.refreshSelector).click refreshFnc
      
      # if table rendered event
      tblParams.onLoad self  if tblParams.onLoad
      return

    "#" + tableId