/* jshint strict: true */
(function(gui, $, undefined) {
    "use strict";
    // "public" methods
    gui.doLog = function() {
        if (gui.debug) {
            try {
                console.log(arguments);
            } catch (e) {
                // nothing can be logged
            }
        }
    };
    
    gui.config = gui.config || {};
    
    // Several convenience "constants" for tables
    gui.config.dataTablesLanguage = {
        'sLengthMenu' : gettext('_MENU_ records per page'),
        'sZeroRecords' : gettext('Empty'),
        'sInfo' : gettext('Records _START_ to _END_ of _TOTAL_'),
        'sInfoEmpty' : gettext('No records'),
        'sInfoFiltered' : gettext('(filtered from _MAX_ total records)'),
        'sProcessing' : gettext('Please wait, processing'),
        'sSearch' : gettext('Filter'),
        'sInfoThousands' : django.formats.THOUSAND_SEPARATOR,
        'oPaginate' : {
            'sFirst' : gettext('First'),
            'sLast' : gettext('Last'),
            'sNext' : gettext('Next'),
            'sPrevious' : gettext('Previous'),
        }
    };
    
    gui.config.dataTableButtons = {
        'new': {
            text: '<span class="fa fa-pencil"></span> <span class="label-tbl-button">' + gettext('New') + '</span>',
            css: 'btn3d btn3d-primary btn3d-tables',
        },
        'edit': { 
            text: '<span class="fa fa-edit"></span> <span class="label-tbl-button">' + gettext('Edit') + '</span>',
            css: 'disabled btn3d-default btn3d btn3d-tables',
        },
        'delete': {
            text: '<span class="fa fa-eraser"></span> <span class="label-tbl-button">' + gettext('Delete') + '</span>',
            css: 'disabled btn3d-default btn3d btn3d-tables',
        },
        'refresh': {
            text: '<span class="fa fa-refresh"></span> <span class="label-tbl-button">' + gettext('Refresh') + '</span>',
            css: 'btn3d-primary btn3d btn3d-tables',
        },
        'xls': {
            text: '<span class="fa fa-save"></span> <span class="label-tbl-button">' + gettext('Xls') + '</span>',
            css: 'btn3d-info btn3d btn3d-tables',
        },
    };
    
    gui.table = function(title, table_id, options) {
        options = options || {};
        var size = options.size || 12;
        var panelId = 'panel-' + table_id;

        return {
           text: api.templates.evaluate('tmpl_table', {
                     panelId: panelId,
                     icon: options.icon || 'table',
                     size: options.size || 12,
                     title: title,
                     table_id: table_id
                 }),
           panelId: panelId,
           refreshSelector: '#' + panelId + ' span.fa-refresh'
        };
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
    
    gui.minimizePanel = function(panelId) {
        var title = $(panelId).attr('data-minimized');
        $(panelId).hide('slow', function(){
            $('<span class="label label-primary panel-icon"><b class="fa fa-plus-square-o"></b> ' + title + '</span>')
                .appendTo('#minimized')
                .click(function(){
                    this.remove();
                    $(panelId).show('slow');
                });
        });
    };

    gui.modal = function(id, title, content) {
        return api.templates.evaluate('tmpl_modal', {
            id: id,
            title: title,
            content: content
        });
    };
    
    gui.launchModal = function(title, content, onSuccess) {
        var id = Math.random().toString().split('.')[1];
        gui.appendToWorkspace(gui.modal(id, title, content));
        id = '#' + id; // for jQuery
        // For "beauty" switches, initialize them now
        $(id + ' .make-switch').bootstrapSwitch();
        // Activate "cool" selects
        $(id + ' .selectpicker').selectpicker();
        // TEST: cooller on mobile devices
        if( /Android|webOS|iPhone|iPad|iPod|BlackBerry/i.test(navigator.userAgent) ) {
            $(id + ' .selectpicker').selectpicker('mobile');
            }        
        // Activate tooltips
        $(id + ' [data-toggle="tooltip"]').tooltip({delay: 500, placement: 'auto right'});
        // And catch "accept" (default is "Save" in fact) button click
        $(id + ' .button-accept').click(function(){
            if( onSuccess ) {
                if( onSuccess(id + ' form') === false ) // Some error may have ocurred, do not close dialog 
                    return;
            }
            $(id).modal('hide');
        });
        
        // Launch modal
        $(id).modal()
             .on('hidden.bs.modal', function () {
                 $(id).remove();
             });
    };
    
    gui.clearWorkspace = function() {
        $('#content').empty();
        $('#minimized').empty();
    };

    gui.appendToWorkspace = function(data) {
        $(data).appendTo('#content');
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
        this.rest.types(function(data) {
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
        console.log('Types: ', this.types);
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
        this.rest.tableInfo(function(data) {
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
            // Generate styles for responsible table, just the name of fields (append header to table)
            var respStyles = [];
            var counter = 0;
            $.each(columns, function(col, value) {
                if( value.bVisible === false )
                    return;
                counter += 1;
                respStyles.push('#' + tableId + ' td:nth-of-type(' + counter + '):before { content: "' + 
                        (value.sTitle || '') + '";}\n');
            });
            // If styles already exists, remove them before adding new ones
            $('style-' + tableId).remove();
            $('<style id="style-' + tableId + '" media="screen">@media (max-width: 768px) { ' + respStyles.join('') + '};</style>').appendTo('head');

            $this.rest.overview(function(data) {
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
                        if( data.length > 1000 )
                            api.tools.blockUI();
                        
                        $this.rest.overview(function(data) {
                                /*$(btn).removeClass('disabled').width('').html(saved);*/
                                setTimeout( function() {
                                    tbl.fnClearTable();
                                    tbl.fnAddData(data);
                                    onRefresh($this);
                                    api.tools.unblockUI();
                                }, 0);
                            });
                        return false; // This may be used on button or href, better disable execution of it
                    };
                    
                    var btns = [];
                    
                    if (options.buttons) {
                        var clickHandlerFor = function(handler, action, newHandler) {
                            var handleFnc = handler || function(val, action, tbl) {gui.doLog('Default handler called for ', action);};
                            return function(btn) {
                                var tbl = $('#' + tableId).dataTable();
                                var val = this.fnGetSelectedData()[0];
                                setTimeout(function() {
                                    if( newHandler ) {
                                        if( handleFnc(action, tbl) === true ) // Reload table?
                                            refreshFnc();
                                    } else {
                                        if( handleFnc(val, action, tbl) === true ) // Reload table?
                                            refreshFnc();
                                    }
                                }, 0);
                            };
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
                                if(Object.keys($this.types).length === 0) {
                                    btn = {
                                        "sExtends" : "text",
                                        "sButtonText" : gui.config.dataTableButtons['new'].text,
                                        "fnClick" : clickHandlerFor(options.onNew, 'new'),
                                        "sButtonClass" : gui.config.dataTableButtons['new'].css,
                                    };
                                } else {
                                    // This table has "types, so we create a dropdown with Types
                                    var newButtons = [];
                                    $.each($this.types, function(i, val){
                                       newButtons.push({
                                               "sExtends" : "text",
                                               "sButtonText" : '<span class="' + val.css + '"></span> ' + val.name,
                                               "fnClick" : clickHandlerFor(options.onNew, i, true),
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
                                    "sButtonClass" : gui.config.dataTableButtons.xls.css,
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
                    $('#' + tableId + '_filter input').addClass('form-control');
                    // Add refresh action to panel
                    $(table.refreshSelector).click(refreshFnc);
                    
                    if (options.scrollToTable === true ) {
                        var tableTop = $('#' + tableId).offset().top;
                        $('html, body').scrollTop(tableTop);
                    }
                    // if table rendered event
                    if( options.onLoad ) {
                        options.onLoad($this);
                    }
                });
            });
        return '#' + tableId;
    }

};
