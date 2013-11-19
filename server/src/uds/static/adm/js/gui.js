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

    // Several convenience "constants"
    gui.dataTablesLanguage = {
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
    table : function(options) {
        "use strict";
        // Options (all are optionals)
        // rowSelect: 'single' or 'multi'
        // container: ID of the element that will hold this table (will be
        // emptied)
        // rowSelectFnc: function to invoke on row selection. receives 1 array -
        // node : TR elements that were selected
        // rowDeselectFnc: function to invoke on row deselection. receives 1
        // array - node : TR elements that were selected
        gui.doLog('Composing table for ' + this.name);
        var tableId = this.name + '-table';
        var $this = this;

        // Empty cells transform
        var renderEmptyCell = function(data) {
            if( data === '' )
                return '-';
            return data;
        };

        // Datetime renderer (with specified format)
        var renderDate = function(format) {
            return function(data, type, full) {
                return strftime(format, new Date(data*1000));
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
                    var options = value[v];
                    var column = {
                        mData : v,
                    };
                    column.sTitle = options.title;
                    column.mRender = renderEmptyCell;
                    if (options.type !== undefined) {
                        switch(options.type) {
                            case 'date':
                                column.sType = 'date';
                                column.mRender = renderDate(djangoFormat(get_format('SHORT_DATE_FORMAT')));
                                break;
                            case 'datetime':
                                column.sType = 'date';
                                column.mRender = renderDate(djangoFormat(get_format('SHORT_DATETIME_FORMAT')));
                                break;
                            case 'time':
                                column.mRender = renderDate(djangoFormat(get_format('TIME_FORMAT')));
                                break;
                            case 'iconType':
                                //columnt.sType = 'html'; // html is default, so this is not needed
                                column.mRender = renderTypeIcon;
                                break;
                            case 'icon':
                                if( options.icon !== undefined ) {
                                    column.mRender = renderIcon(options.icon);
                                }
                                break;
                            case 'dict':
                                if( options.dict !== undefined ) {
                                    column.mRender = renderTextTransform(options.dict);
                                }
                                break;
                            default:
                                column.sType = options.type;
                        }
                    }
                    if (options.width)
                        column.sWidth = options.width;
                    if (options.visible !== undefined)
                        column.bVisible = options.visible;
                    if (options.sortable !== undefined)
                        column.bSortable = options.sortable;
                    if (options.searchable !== undefined)
                        column.bSearchable = options.searchable;
                    columns.push(column);
                }
            });
            // Generate styles for responsibe table, just the name of fields
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

                        // methods for buttons click
                        var editFnc = function() {
                            gui.doLog('Edit');
                            gui.doLog(this);
                        };
                        var deleteFnc = function() {
                            gui.doLog('Delete');
                            gui.doLog(this);
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
                            case 'edit':
                                btn = {
                                    "sExtends" : "text",
                                    "sButtonText" : gettext('Edit'),
                                    "fnSelect" : editSelected,
                                    "fnClick" : editFnc,
                                    "sButtonClass" : "disabled btn3d btn3d-tables"
                                };
                                break;
                            case 'delete':
                                btn = {
                                    "sExtends" : "text",
                                    "sButtonText" : gettext('Delete'),
                                    "fnSelect" : deleteSelected,
                                    "fnClick" : deleteFnc,
                                    "sButtonClass" : "disabled btn3d btn3d-tables"
                                };
                                break;
                            case 'refresh':
                                btn = {
                                    "sExtends" : "text",
                                    "sButtonText" : gettext('Refresh'),
                                    "fnClick" : refreshFnc,
                                    "sButtonClass" : "btn3d-primary btn3d btn3d-tables"
                                };
                                break;
                            case 'xls':
                                btn = {
                                    "sExtends" : "text",
                                    "sButtonText" : 'xls',
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
                                            // window.location.href = uri + base64(api.templates.evaluate(tmpl, ctx));
                                            setTimeout( function() {
                                                saveAs(new Blob([api.templates.evaluate(tmpl, ctx)], 
                                                        {type: 'application/vnd.ms-excel'} ), title + '.xls')
                                            }, 20);
                                        });
                                    },
                                    "sButtonClass" : "btn3d-info btn3d btn3d-tables"
                                };
                            /*case 'csv': 
                                btn = {
                                    "sExtends" : "csv",
                                    "sTitle" : title,
                                    "sFileName" : title + '.csv',
                                };
                                break;*/
                            /*case 'pdf':
                                btn = {
                                    "sExtends" : "pdf",
                                    "sTitle" : title,
                                    "sPdfMessage" : "Summary Info",
                                    "fnCellRender": function(value, col, node, dattaIndex) {
                                        // All tables handled by this needs an "id" on col 0
                                        // So, we return empty values for col 0
                                        if(col === 0)
                                            return '';
                                        return value.toString().replace(/(<([^>]+)>)/ig, '');
                                    },
                                    "sFileName" : title + '.pdf',
                                    "sPdfOrientation" : "portrait"
                                };
                                break;*/
                            }

                            if (btn !== undefined)
                                btns.push(btn);
                        });
                    }

                    // Initializes oTableTools
                    var oTableTools = {
                        "aButtons" : btns
                    };
                    if (options.rowSelect) {
                        oTableTools.sRowSelect = options.rowSelect;
                    }
                    if (options.onRowSelect) {
                        oTableTools.fnRowSelected = options.onRowSelect;
                    }
                    if (options.onRowDeselect) {
                        oTableTools.fnRowDeselected = options.onRowDeselect;
                    }

                    $('#' + tableId).dataTable({
                        "aaData" : data,
                        "aoColumns" : columns,
                        "oLanguage" : gui.dataTablesLanguage,
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
                    if (options.scroll !== undefined ) {
                        var tableTop = $('#' + tableId).offset().top;
                        $('html, body').scrollTop(tableTop);
                    }
                    // if table rendered event
                    if( options.onLoad ) {
                        options.onLoad($this);
                    }
                }
            });
        });
        return '#' + tableId;
    }

};
