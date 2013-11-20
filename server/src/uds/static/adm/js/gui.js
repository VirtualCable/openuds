/* jshint strict: true */
(function(gui, $, undefined) {
    "use strict";
    // "public" methods
    gui.doLog = function(data) {
        if (gui.debug) {
            try {
                console.log(data);
            } catch (e) {
                // nothing can be logged
            }

        }
    };
    
    gui.config = gui.config || {};
    
    // Several convenience "constants" for tables
    gui.config.dataTablesLanguage = {
        "sLengthMenu" : gettext("_MENU_ records per page"),
        "sZeroRecords" : gettext("Empty"),
        "sInfo" : gettext("Records _START_ to _END_ of _TOTAL_"),
        "sInfoEmpty" : gettext("No records"),
        "sInfoFiltered" : gettext("(filtered from _MAX_ total records)"),
        "sProcessing" : gettext("Please wait, processing"),
        "sSearch" : gettext("Filter"),
        "sInfoThousands" : django.formats.THOUSAND_SEPARATOR,
        "oPaginate" : {
            "sFirst" : gettext("First"),
            "sLast" : gettext("Last"),
            "sNext" : gettext("Next"),
            "sPrevious" : gettext("Previous"),
        }
    };
    
    gui.config.dataTableButtonsText = {
        'new': '<span class="fa fa-pencil"></span> <span class="label-tbl-button">' + gettext('New') + '</span>',
        'edit': '<span class="fa fa-edit"></span> <span class="label-tbl-button">' + gettext('Edit') + '</span>',
        'delete': '<span class="fa fa-eraser"></span> <span class="label-tbl-button">' + gettext('Delete') + '</span>',
        'refresh': '<span class="fa fa-refresh"></span> <span class="label-tbl-button">' + gettext('Refresh') + '</span>',
        'xls': '<span class="fa fa-save"></span> <span class="label-tbl-button">' + gettext('Xls') + '</span>',
    };

    gui.table = function(title, table_id, options) {
        if (options === undefined)
            options = {
                'size' : 12,
                'icon' : 'table'
            };
        if (options.size === undefined)
            options.size = 12;
        if (options.icon === undefined)
            options.icon = 'table';

        return '<div class="panel panel-primary"><div class="panel-heading">' +
                '<h3 class="panel-title"><span class="fa fa-' + options.icon + '"></span> ' + title + '</h3></div>' +
                '<div class="panel-body"><table class="table table-striped table-bordered table-hover" id="' +
                table_id + '" border="0" cellpadding="0" cellspacing="0" width="100%"></table></div></div>';
    };

    gui.breadcrumbs = function(path) {
        var items = path.split('/');
        var active = items.pop();
        var list = '';
        $.each(items, function(index, value) {
            list += '<li><a href="#">' + value + '</a></li>';
        });
        list += '<li class="active">' + active + '</li>';

        return '<div class="row"><div class="col-lg-12"><ol class="breadcrumb">' + list + "</ol></div></div>";
    };

    gui.clearWorkspace = function() {
        $('#page-wrapper').empty();
    };

    gui.appendToWorkspace = function(data) {
        $(data).appendTo('#page-wrapper');
    };

    // Links methods

    gui.deployed_services = function() {
        gui.clearWorkspace();
        gui.appendToWorkspace(gui.breadcrumbs(gettext('Deployed services')));
    };

    gui.setLinksEvents = function() {
        var sidebarLinks = [ {
            id : 'lnk-dashboard',
            exec : gui.dashboard.link,
        }, {
            id : 'lnk-service_providers',
            exec : gui.providers.link
        }, {
            id : 'lnk-authenticators',
            exec : gui.authenticators.link
        }, {
            id : 'lnk-osmanagers',
            exec : gui.osmanagers.link
        }, {
            id : 'lnk-connectivity',
            exec : gui.connectivity.link
        }, {
            id : 'lnk-deployed_services',
            exec : gui.deployed_services
        }, ];
        $.each(sidebarLinks, function(index, value) {
            gui.doLog('Adding ' + value.id);
            $('.' + value.id).unbind('click').click(function(event) {
                if ($('.navbar-toggle').css('display') != 'none') {
                    $(".navbar-toggle").trigger("click");
                }
                $('html, body').scrollTop(0);
                value.exec(event);
            });
        });
    };

    gui.init = function() {
        gui.setLinksEvents();
        gui.dashboard.link();
    };

    // Public attributes
    gui.debug = true;
}(window.gui = window.gui || {}, jQuery));

function BasicGuiElement(name) {
    "use strict";
    this.name = name;
}

function GuiElement(restItem, name) {
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
        var $this = this;
        this.rest.types({
            success: function(data) {
                var styles = '';
                $.each(data, function(index, value) {
                    var className = $this.name + '-' + value.type;
                    $this.types[value.type] = {
                        css : className,
                        name : value.name || '',
                        description : value.description || ''
                    };
                    gui.doLog('Creating style for ' + className);
                    var style = '.' + className + ' { display:inline-block; background: url(data:image/png;base64,' +
                            value.icon + '); ' + 'width: 16px; height: 16px; vertical-align: middle; } ';
                    styles += style;
                });
                if (styles !== '') {
                    styles = '<style media="screen">' + styles + '</style>';
                    $(styles).appendTo('head');
                }
            },
        });
    },
    // Options: dictionary
    //   container: container ID of parent for the table. If undefined, table will be appended to workspace
    //   buttons: array of visible buttons (strings), valid are [ 'new', 'edit', 'refresh', 'delete', 'xls' ],
    //   rowSelect: type of allowed row selection, valid values are 'single' and 'multi'
    //   scrollToTable: if True, will scroll page to show table
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
    //                   3.- the DataTableTools that raised the event
    //   onNew: Event (function). If defined, will be invoked when "new" button is pressed
    //                Receives 4 parameters:
    //                   1.- the selected item data (single object, as got from api...get)
    //                   2.- the event that fired this (new, delete, edit, ..)
    //                   3.- the DataTable that raised the event
    //                   4.- the DataTableTools that raised the event
    //   onEdit: Event (function). If defined, will be invoked when "edit" button is pressed
    //                Receives 4 parameters:
    //                   1.- the selected item data (single object, as got from api...get)
    //                   2.- the event that fired this (new, delete, edit, ..)
    //                   3.- the DataTable that raised the event
    //                   4.- the DataTableTools that raised the event
    //   onDelete: Event (function). If defined, will be invoked when "delete" button is pressed
    //                Receives 4 parameters:
    //                   1.- the selected item data (single object, as got from api...get)
    //                   2.- the event that fired this (new, delete, edit, ..)
    //                   4.- the DataTable that raised the event
    //                   5.- the DataTableTools that raised the event
    table : function(options) {
        "use strict";
        options = options || {};
        gui.doLog('Composing table for ' + this.name);
        var tableId = this.name + '-table';
        var $this = this; // Store this for child functions

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
                var css = $this.types[value.type].css;
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
        this.rest.tableInfo({
            success: function(data) {
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
                        
                        if (opts.type !== undefined && column.bVisible ) {
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
                // Generate styles for responsible table, just the name of fields
                var respStyles = [];
                var counter = 0;
                $.each(columns, function(col, value) {
                    if( value.bVisible === false )
                        return;
                    counter += 1;
                    respStyles.push('#' + tableId + ' td:nth-of-type(' + counter + '):before { content: "' + 
                            (value.sTitle || '') + '";}\n');
                    respStyles.push('#' + tableId + ' td:nth-of-type(' + counter + '):empty { background-color: red ;}\n');
                });
                // If styles already exists, remove them before adding new ones
                $('style-' + tableId).remove();
                $('<style id="style-' + tableId + '" media="screen">@media (max-width: 979px) { ' + respStyles.join('') + '};</style>').appendTo('head');
    
                $this.rest.get({
                    success : function(data) {
                        var table = gui.table(title, tableId);
                        if (options.container === undefined) {
                            gui.appendToWorkspace('<div class="row"><div class="col-lg-12">' + table + '</div></div>');
                        } else {
                            $('#' + options.container).empty();
                            $('#' + options.container).append(table);
                        }
    
                        var btns = [];
    
                        if (options.buttons) {
                            var clickHandlerFor = function(handler, action) {
                                var handleFnc = handler || function(val, action, tbl, tbltools) {gui.doLog('Default handler called for ' + action + ': ' + JSON.stringify(val));};
                                return function(btn) {
                                    var tblTools = this;
                                    var table = $('#' + tableId).dataTable();
                                    var val = this.fnGetSelectedData()[0];
                                    setTimeout(function() {
                                        handleFnc(val, action, table, tblTools);
                                    }, 0);
                                };
                            };
    
                            // What execute on refresh button push
                            var onRefresh = options.onRefresh || function(){};
    
                            var refreshFnc = function(btn) {
                                // Refreshes table content
                                var tbl = $('#' + tableId).dataTable();
                                /*var width = $(btn).width();
                                var saved = $(btn).html();
                                $(btn).addClass('disabled').html('<span class="fa fa-spinner fa-spin"></span>')
                                        .width(width);*/
                                if( data.length > 1000 )
                                    api.tools.blockUI();
                                
                                onRefresh($this);
                                
                                $this.rest.get({
                                    success : function(data) {
                                        /*$(btn).removeClass('disabled').width('').html(saved);*/
                                        setTimeout( function() {
                                            tbl.fnClearTable();
                                            tbl.fnAddData(data);
                                            api.tools.unblockUI();
                                        }, 0);
                                    }
                                });
                            };
    
                            // methods for buttons on row select
                            var editSelected = function(btn, obj, node) {
                                var sel = this.fnGetSelectedData();
                                if (sel.length == 1) {
                                    $(btn).removeClass('disabled').addClass('btn3d-success');
                                } else {
                                    $(btn).removeClass('btn3d-success').addClass('disabled');
                                }
                            };
                            var deleteSelected = function(btn, obj, node) {
                                var sel = this.fnGetSelectedData();
                                if (sel.length > 0) {
                                    $(btn).removeClass('disabled').addClass('btn3d-warning');
                                } else {
                                    $(btn).removeClass('btn3d-warning').addClass('disabled');
                                }
                            };
    
                            $.each(options.buttons, function(index, value) {
                                var btn;
                                switch (value) {
                                case 'new':
                                    btn = {
                                        "sExtends" : "text",
                                        "sButtonText" : gui.config.dataTableButtonsText['new'],
                                        "fnSelect" : deleteSelected,
                                        "fnClick" : clickHandlerFor(options.onDelete, 'delete'),
                                        "sButtonClass" : "disabled btn3d btn3d-tables"
                                    };
                                    break;
                                case 'edit':
                                    btn = {
                                        "sExtends" : "text",
                                        "sButtonText" : gui.config.dataTableButtonsText['edit'],
                                        "fnSelect" : editSelected,
                                        "fnClick" : clickHandlerFor(options.onEdit, 'edit'),
                                        "sButtonClass" : "disabled btn3d btn3d-tables"
                                    };
                                    break;
                                case 'delete':
                                    btn = {
                                        "sExtends" : "text",
                                        "sButtonText" : gui.config.dataTableButtonsText['delete'],
                                        "fnSelect" : deleteSelected,
                                        "fnClick" : clickHandlerFor(options.onDelete, 'delete'),
                                        "sButtonClass" : "disabled btn3d btn3d-tables"
                                    };
                                    break;
                                case 'refresh':
                                    btn = {
                                        "sExtends" : "text",
                                        "sButtonText" : gui.config.dataTableButtonsText['refresh'],
                                        "fnClick" : refreshFnc,
                                        "sButtonClass" : "btn3d-primary btn3d btn3d-tables"
                                    };
                                    break;
                                case 'xls':
                                    btn = {
                                        "sExtends" : "text",
                                        "sButtonText" : gui.config.dataTableButtonsText['xls'],
                                        "fnClick" : function(){
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
                                                $.each(data, function(index, row) {
                                                    var cells = [];
                                                    $.each(columns, function(index, col){
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
                                                setTimeout( function() {
                                                    saveAs(new Blob([api.templates.evaluate(tmpl, ctx)], 
                                                            {type: 'application/vnd.ms-excel'} ), title + '.xls');
                                                }, 20);
                                            });
                                        },
                                        "sButtonClass" : "btn3d-info btn3d btn3d-tables"
                                    };
                                }
    
                                if (btn !== undefined)
                                    btns.push(btn);
                            });
                        }
    
                        // Initializes oTableTools
                        var oTableTools = {
                            "aButtons" : btns
                        };
                        
                        // Type of row selection 
                        if (options.rowSelect) {
                            oTableTools.sRowSelect = options.rowSelect;
                        }
                        
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
    
                        });
                        // Fix 3dbuttons
                        api.tools.fix3dButtons('#' + tableId + '_wrapper .btn-group-3d');
                        // Fix form 
                        //$('#' + tableId + '_filter input').addClass('form-control');
                        if (options.scrollToTable === true ) {
                            var tableTop = $('#' + tableId).offset().top;
                            $('html, body').scrollTop(tableTop);
                        }
                        // if table rendered event
                        if( options.onLoad ) {
                            options.onLoad($this);
                        }
                    }
                });
            },
            
        });
        return '#' + tableId;
    }

};
