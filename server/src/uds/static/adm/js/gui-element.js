/* jshint strict: true */
// Operations commmon to most elements
function BasicGuiElement(name) {
    "use strict";
    this.name = name;
}

function GuiElement(restItem, name, typesFunction) {
    "use strict";
    this.rest = restItem;
    this.name = name;
    this.types = {};
    this.init();
}

// all gui elements has, at least, name && type
// Types must include, at least: type, icon
GuiElement.prototype = {
    init : function() {
        "use strict";
        gui.doLog('Initializing ' + this.name);
        var self = this;
        this.rest.types(function(data) {
                var styles = '';
                var alreadyAttached =  $('#gui-style-'+self.name).length !== 0;
                $.each(data, function(index, value) {
                    var className = self.name + '-' + value.type;
                    self.types[value.type] = {
                        css : className,
                        name : value.name || '',
                        description : value.description || ''
                    };
                    gui.doLog('Creating style for ' + className);
                    if( !alreadyAttached ) {
                        var style = '.' + className + ' { display:inline-block; background: url(data:image/png;base64,' +
                                value.icon + '); ' + 'width: 16px; height: 16px; vertical-align: middle; } ';
                        styles += style;
                    }
                });
                if (styles !== '') {
                    // If style already attached, do not re-attach it
                    styles = '<style id="gui-style-' + self.name + '" media="screen">' + styles + '</style>';
                    $(styles).appendTo('head');
                }
            });
    },
    
    // Options: dictionary
    //   container: container ID of parent for the table. If undefined, table will be appended to workspace
    //   buttons: array of visible buttons (strings), valid are [ 'new', 'edit', 'refresh', 'delete', 'xls' ],
    //   rowSelect: type of allowed row selection, valid values are 'single' and 'multi'
    //   scrollToTable: if True, will scroll page to show table
    //   deferedRender: if True, datatable will be created with "bDeferRender": true, that will improve a lot creation
    //   
    //   onLoad: Event (function). If defined, will be invoked when table is fully loaded.
    //           Receives 1 parameter, that is the gui element (GuiElement) used to render table
    //   onRowSelect: Event (function). If defined, will be invoked when a row of table is selected
    //                Receives 3 parameters:
    //                   1.- the array of selected items data (objects, as got from api...get)
    //                   2.- the DataTable that raised the event
    //                   3.- the DataTableTools that raised the event
    //   onRowDeselect: Event (function). If defined, will be invoked when a row of table is deselected
    //                Receives 3 parameters:
    //                   1.- the array of selected items data (objects, as got from api...get)
    //                   2.- the DataTable that raised the event
    //   onCheck:    Event (function), 
    //               It determines the state of buttons on selection: if returns "true", the indicated button will be enabled, and disabled if returns "false"
    //               Receives 2 parameters:
    //                   1.- the event fired, that can be "edit" or "delete"
    //                   2.- the selected items data (array of selected elements, as got from api...get. In case of edit, array length will be 1)
    //   onNew: Event (function). If defined, will be invoked when "new" button is pressed
    //                Receives 4 parameters:
    //                   1.- the selected item data (single object, as got from api...get)
    //                   2.- the event that fired this (new, delete, edit, ..)
    //                   3.- the DataTable that raised the event
    //   onEdit: Event (function). If defined, will be invoked when "edit" button is pressed
    //                Receives 4 parameters:
    //                   1.- the selected item data (single object, as got from api...get)
    //                   2.- the event that fired this (new, delete, edit, ..)
    //                   3.- the DataTable that raised the event
    //   onDelete: Event (function). If defined, will be invoked when "delete" button is pressed
    //                Receives 4 parameters:
    //                   1.- the selected item data (single object, as got from api...get)
    //                   2.- the event that fired this (new, delete, edit, ..)
    //                   4.- the DataTable that raised the event
    table : function(options) {
        "use strict";
        gui.doLog('Types: ', this.types);
        options = options || {};
        gui.doLog('Composing table for ' + this.name);
        var tableId = this.name + '-table';
        var self = this; // Store this for child functions

        // ---------------
        // Cells renderers
        // ---------------
        
        // Empty cells transform
        var renderEmptyCell = function(data) {
            if( data === '' )
                return '-';
            return data;
        };

        // Datetime renderer (with specified format)
        var renderDate = function(format) {
            return function(data, type, full) {
                return api.tools.strftime(format, new Date(data*1000));
            };
        };
        
        // Icon renderer, based on type (created on init methods in styles)
        var renderTypeIcon = function(data, type, value){
            if( type == 'display' ) {
                self.types[value.type] = self.types[value.type] || {};
                var css = self.types[value.type].css || 'fa fa-asterisk';
                return '<span class="' + css + '"></span> ' + renderEmptyCell(data);
            } else {
                return renderEmptyCell(data);
            }
        };
        
        // Custom icon renderer, in fact span with defined class
        var renderIcon = function(icon) {
            return function(data, type, full) {
                if( type == 'display' ) {
                    return '<span class="' + icon + '"></span> ' + renderEmptyCell(data);
                } else {
                    return renderEmptyCell(data);
                }
            };
        };
        // Text transformation, dictionary based
        var renderTextTransform = function(dict) {
            return function(data, type, full) {
                    return dict[data] || renderEmptyCell('');
            };
        };
        
        this.rest.tableInfo(function(data) { // Gets tableinfo data (columns, title, visibility of fields, etc...
            var title = data.title;
            var columns = [];
            $.each(data.fields, function(index, value) {
                for ( var v in value) {
                    var opts = value[v];
                    var column = {
                        mData : v,
                    };
                    column.sTitle = opts.title;
                    column.mRender = renderEmptyCell;
                    if (opts.width)
                        column.sWidth = opts.width;
                    column.bVisible = opts.visible === undefined ? true : opts.visible;
                    if (opts.sortable !== undefined)
                        column.bSortable = opts.sortable;
                    if (opts.searchable !== undefined)
                        column.bSearchable = opts.searchable;
                    
                    if (opts.type && column.bVisible ) {
                        switch(opts.type) {
                            case 'date':
                                column.sType = 'date';
                                column.mRender = renderDate(api.tools.djangoFormat(get_format('SHORT_DATE_FORMAT')));
                                break;
                            case 'datetime':
                                column.sType = 'date';
                                column.mRender = renderDate(api.tools.djangoFormat(get_format('SHORT_DATETIME_FORMAT')));
                                break;
                            case 'time':
                                column.mRender = renderDate(api.tools.djangoFormat(get_format('TIME_FORMAT')));
                                break;
                            case 'iconType':
                                //columnt.sType = 'html'; // html is default, so this is not needed
                                column.mRender = renderTypeIcon;
                                break;
                            case 'icon':
                                if( opts.icon !== undefined ) {
                                    column.mRender = renderIcon(opts.icon);
                                }
                                break;
                            case 'dict':
                                if( opts.dict !== undefined ) {
                                    column.mRender = renderTextTransform(opts.dict);
                                }
                                break;
                            default:
                                column.sType = opts.type;
                        }
                    }
                    columns.push(column);
                }
            });
            // Responsive style for tables, using tables.css and this code generates the "titles" for vertical display on small sizes
            $('#style-' + tableId).remove();  // Remove existing style for table before adding new one
            $(api.templates.evaluate('tmpl_responsive_table', {
                tableId: tableId,
                columns: columns,
            })).appendTo('head');

            self.rest.overview(function(data) { // Gets "overview" data for table (table contents, but resume form)
                    var table = gui.table(title, tableId);
                    if (options.container === undefined) {
                        gui.appendToWorkspace('<div class="row"><div class="col-lg-12">' + table.text + '</div></div>');
                    } else {
                        $('#' + options.container).empty();
                        $('#' + options.container).append(table.text);
                    }

                    // What execute on refresh button push
                    var onRefresh = options.onRefresh || function(){};

                    var refreshFnc = function() {
                        // Refreshes table content
                        var tbl = $('#' + tableId).dataTable();
                        // Clears selection first
                        TableTools.fnGetInstance(tableId).fnSelectNone();
                        //if( data.length > 1000 )
                        gui.tools.blockUI();
                        
                        self.rest.overview(function(data) {  // Restore overview
                                setTimeout( function() {
                                    tbl.fnClearTable();
                                    tbl.fnAddData(data);
                                    onRefresh(self);
                                    gui.tools.unblockUI();
                                }, 0);
                            });  // End restore overview
                        return false; // This may be used on button or href, better disable execution of it
                    };
                    
                    var btns = [];
                    
                    if (options.buttons) {
                        // Generic click handler generator for this table
                        var clickHandlerFor = function(handler, action, newHandler) {
                            var handleFnc = handler || function(val, action, tbl) {gui.doLog('Default handler called for ', action);};
                            return function(btn) {
                                var tbl = $('#' + tableId).dataTable();
                                var val = this.fnGetSelectedData()[0];
                                setTimeout(function() {
                                    if( newHandler ) {
                                        handleFnc(action, tbl, refreshFnc);
                                    } else {
                                        handleFnc(val, action, tbl, refreshFnc);
                                    }
                                }, 0);
                            };
                        };

                        var onCheck = options.onCheck || function(){ return true; }; // Default oncheck always returns true
                        
                        // methods for buttons on row select
                        var editSelected = function(btn, obj, node) {
                            var sel = this.fnGetSelectedData();
                            var enable = sel.length == 1 ? onCheck("edit", sel) : false;
                            
                            if ( enable) {
                                $(btn).removeClass('disabled').addClass('btn3d-success');
                            } else {
                                $(btn).removeClass('btn3d-success').addClass('disabled');
                            }
                        };
                        var deleteSelected = function(btn, obj, node) {
                            var sel = this.fnGetSelectedData();
                            var enable = sel.length == 1 ? onCheck("delete", sel) : false;
                            
                            if (enable) {
                                $(btn).removeClass('disabled').addClass('btn3d-warning');
                            } else {
                                $(btn).removeClass('btn3d-warning').addClass('disabled');
                            }
                        };
                        
                        $.each(options.buttons, function(index, value) { // Iterate through button definition
                            var btn;
                            switch (value) {
                            case 'new':
                                if(Object.keys(self.types).length === 0) {
                                    btn = {
                                        "sExtends" : "text",
                                        "sButtonText" : gui.config.dataTableButtons['new'].text,
                                        "fnClick" : clickHandlerFor(options.onNew, 'new'),
                                        "sButtonClass" : gui.config.dataTableButtons['new'].css,
                                    };
                                } else {
                                    // This table has "types, so we create a dropdown with Types
                                    var newButtons = [];
                                    // Order buttons by name, much more easy for users... :-)
                                    var order = [];
                                    $.each(self.types, function(k, v){
                                       order.push({
                                           type: k,
                                           css: v.css,
                                           name: v.name,
                                           description: v.description,
                                       }); 
                                    });
                                    $.each(order.sort(function(a,b){return a.name.localeCompare(b.name);}), function(i, val){
                                       newButtons.push({
                                               "sExtends" : "text",
                                               "sButtonText" : '<span class="' + val.css + '"></span> <span data-toggle="tooltip" data-title="' + val.description + '">' + val.name + '</span>',
                                               "fnClick" : clickHandlerFor(options.onNew, val.type, true),
                                       });
                                    });
                                    btn = {
                                            "sExtends" : "collection",
                                            "aButtons":  newButtons,
                                            "sButtonText" : gui.config.dataTableButtons['new'].text,
                                            "sButtonClass" : gui.config.dataTableButtons['new'].css,
                                        };
                                }
                                break;
                            case 'edit':
                                btn = {
                                    "sExtends" : "text",
                                    "sButtonText" : gui.config.dataTableButtons.edit.text,
                                    "fnSelect" : editSelected,
                                    "fnClick" : clickHandlerFor(options.onEdit, 'edit'),
                                    "sButtonClass" : gui.config.dataTableButtons.edit.css,
                                };
                                break;
                            case 'delete':
                                btn = {
                                    "sExtends" : "text",
                                    "sButtonText" : gui.config.dataTableButtons['delete'].text,
                                    "fnSelect" : deleteSelected,
                                    "fnClick" : clickHandlerFor(options.onDelete, 'delete'),
                                    "sButtonClass" : gui.config.dataTableButtons['delete'].css,
                                };
                                break;
                            case 'refresh':
                                btn = {
                                    "sExtends" : "text",
                                    "sButtonText" : gui.config.dataTableButtons.refresh.text,
                                    "fnClick" : refreshFnc,
                                    "sButtonClass" : gui.config.dataTableButtons.refresh.css,
                                };
                                break;
                            case 'xls':
                                btn = { 
                                    "sExtends" : "text",
                                    "sButtonText" : gui.config.dataTableButtons.xls.text,
                                    "fnClick" : function() {  // Export to excel
                                        api.templates.get('spreadsheet', function(tmpl) {
                                            var styles = { 'bold': 's21', };
                                            var uri = 'data:application/vnd.ms-excel;base64,',
                                                base64 = function(s) { return window.btoa(unescape(encodeURIComponent(s))); };
                                                
                                            var headings = [], rows = [];
                                            $.each(columns, function(index, heading){
                                                if( heading.bVisible === false ) {
                                                    return;
                                                }
                                                headings.push(api.spreadsheet.cell(heading.sTitle, 'String', styles.bold));
                                            });
                                            rows.push(api.spreadsheet.row(headings));
                                            $.each(data, function(index1, row) {
                                                var cells = [];
                                                $.each(columns, function(index2, col){
                                                    if( col.bVisible === false ) {
                                                        return;
                                                    }
                                                    var type = col.sType == 'numeric' ? 'Number':'String';
                                                    cells.push(api.spreadsheet.cell(row[col.mData], type));
                                                });
                                                rows.push(api.spreadsheet.row(cells));
                                            });
                                            var ctx = {
                                                creation_date: (new Date()).toISOString(),
                                                worksheet: title,
                                                columns_count: headings.length,
                                                rows_count: rows.length,
                                                rows: rows.join('\n')
                                            };
                                            gui.doLog(ctx);
                                            setTimeout( function() {
                                                saveAs(new Blob([api.templates.evaluate(tmpl, ctx)], 
                                                        {type: 'application/vnd.ms-excel'} ), title + '.xls');
                                            }, 20);
                                        });
                                    }, // End export to excell
                                    "sButtonClass" : gui.config.dataTableButtons.xls.css,
                                };
                            }

                            if(btn) {
                                btns.push(btn);
                            }
                        });  // End buttoon iteration
                    }

                    // Initializes oTableTools
                    var oTableTools = {
                        "aButtons" : btns,
                        "sRowSelect": options.rowSelect || 'single',
                    };
                    
                    if (options.onRowSelect) {
                        var rowSelectedFnc = options.onRowSelect;
                        oTableTools.fnRowSelected = function() {
                            rowSelectedFnc(this.fnGetSelectedData(), $('#' + tableId).dataTable(), this);
                        };
                    }
                    if (options.onRowDeselect) {
                        var rowDeselectedFnc = options.onRowDeselect;
                        oTableTools.fnRowDeselected = function() {
                            rowDeselectedFnc(this.fnGetSelectedData(), $('#' + tableId).dataTable(), this);
                        };
                    }

                    $('#' + tableId).dataTable({
                        "aaData" : data,
                        "aoColumns" : columns,
                        "oLanguage" : gui.config.dataTablesLanguage,
                        "oTableTools" : oTableTools,
                        // First is upper row,
                        // second row is lower
                        // (pagination) row
                        "sDom" : "<'row'<'col-xs-8'T><'col-xs-4'f>r>t<'row'<'col-xs-5'i><'col-xs-7'p>>",
                        "bDeferRender": options.deferedRender || false,
                    });
                    // Fix 3dbuttons
                    gui.tools.fix3dButtons('#' + tableId + '_wrapper .btn-group-3d');
                    // Fix form 
                    $('#' + tableId + '_filter input').addClass('form-control');
                    // Add refresh action to panel
                    $(table.refreshSelector).click(refreshFnc);
                    // Add tooltips to "new" buttons
                    $('.DTTT_dropdown [data-toggle="tooltip"]').tooltip({
                        container:'body',
                        delay: { show: 1000, hide: 100},
                        placement: 'auto right',
                    });
                    
                    if (options.scrollToTable === true ) {
                        var tableTop = $('#' + tableId).offset().top;
                        $('html, body').scrollTop(tableTop);
                    }
                    // if table rendered event
                    if( options.onLoad ) {
                        options.onLoad(self);
                    }
                }); // End Overview data
            }); // End Tableinfo data
        
        return '#' + tableId;
    },
};
