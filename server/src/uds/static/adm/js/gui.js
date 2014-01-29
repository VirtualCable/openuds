/* jshint strict: true */
(function(gui, $, undefined) {
    "use strict";
    // "public" methods
    gui.doLog = function() {
        if (gui.debug) {
            try {
                console.log.apply(window, arguments);
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
            'sFirst' : '<span class="fa fa-fast-backward "></span> ',
            'sLast' : '<span class="fa fa-fast-forward"></span> ',
            'sNext' : '<span class="fa fa-forward"></span> ',
            'sPrevious' : '<span class="fa fa-backward"></span> ',
        }
    };
    
    gui.config.dataTableButtons = {
        'new': {
            text: '<span class="fa fa-pencil"></span> <span class="label-tbl-button">' + gettext('New') + '</span>',
            css: 'btn btn3d btn3d-primary btn3d-tables',
        },
        'edit': { 
            text: '<span class="fa fa-edit"></span> <span class="label-tbl-button">' + gettext('Edit') + '</span>',
            css: 'btn disabled btn3d-default btn3d btn3d-tables',
        },
        'delete': {
            text: '<span class="fa fa-trash-o"></span> <span class="label-tbl-button">' + gettext('Delete') + '</span>',
            css: 'btn disabled btn3d-default btn3d btn3d-tables',
        },
        'xls': {
            text: '<span class="fa fa-save"></span> <span class="label-tbl-button">' + gettext('Xls') + '</span>',
            css: 'btn btn3d-info btn3d btn3d-tables',
        },
        'custom': { 
            text: null,
            css: 'btn btn3d-default btn3d btn3d-tables',
        },
    };
    
    gui.genRamdonId = function(prefix) {
        prefix = prefix || '';
        return prefix + Math.random().toString().split('.')[1];
    };
    
    gui.table = function(title, table_id, options) {
        options = options || {};
        var panelId = 'panel-' + table_id;

        return {
           text: api.templates.evaluate('tmpl_comp_table', {
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
    
    gui.modal = function(id, title, content, options) {
        options = options || {};
        return api.templates.evaluate('tmpl_comp_modal', {
            id: id,
            title: title,
            content: content,
            footer: options.footer,
            button1: options.closeButton,
            button2: options.actionButton,
            
        });
    };
    
    gui.launchModal = function(title, content, options) {
        options = options || {};
        var id = gui.genRamdonId('modal-'); // Get a random ID for this modal
        gui.appendToWorkspace(gui.modal(id, title, content, options));
        id = '#' + id; // for jQuery
        
        $(id).modal()
        .on('hidden.bs.modal', function () {
            $(id).remove();
        });
        return id;
    };
    
    gui.notify = function(message, type) {
        gui.launchModal('<b class="text-'+ type + '">' + gettext('Message') + '</b>', '<span class="text-' + type + '">' + message + '</span>', {actionButton: ' '});
    };
    
    gui.failRequestModalFnc = function(title) {
        return function(jqXHR, textStatus, errorThrown) { // fail on put
            gui.tools.unblockUI();
            gui.launchModal('<b class="text-danger">' + title + '</b>', jqXHR.responseText, { actionButton: ' '});
        };
    };

    gui.clearWorkspace = function() {
        $('#content').empty();
        $('#minimized').empty();
    };

    gui.appendToWorkspace = function(data) {
        $(data).appendTo('#content');
    };

    // Clean up several "internal" data
    // I have discovered some "items" that are keep in memory, or that adds garbage to body (datatable && tabletools mainly)
    // Whenever we change "section", we clean up as much as we can, so we can keep things as clean as possible
    // Main problem where comming with "tabletools" and keeping references to all instances created
    gui.cleanup = function() {
        gui.doLog('Cleaning up things');
        // Tabletools creates divs at end that do not get removed, here is a good place to ensure there is no garbage left behind
        // And anyway, if this div does not exists, it creates a new one...
        $('.DTTT_dropdown').remove(); // Tabletools keep adding garbage to end of body on each new table creation, so we simply remove it on each new creation
        TableTools._aInstances = []; // Same for internal references
        TableTools._aListeners = [];
        
        // Destroy any created datatable
        $.each($.fn.dataTable.fnTables(), function(undefined, tbl){
            var $tbl = $(tbl).dataTable();
            $tbl.fnClearTable(); // Removing data first makes things much faster
            $tbl.fnDestroy();
        });
    };
    
    gui.setLinksEvents = function() {
        var sidebarLinks = [ 
            {
                id : 'lnk-dashboard',
                exec : gui.dashboard.link,
                cleanup: true,
            }, {
                id : 'lnk-service_providers',
                exec : gui.providers.link,
                cleanup: true,
            }, {
                id : 'lnk-authenticators',
                exec : gui.authenticators.link,
                cleanup: true,
            }, {
                id : 'lnk-osmanagers',
                exec : gui.osmanagers.link,
                cleanup: true,
            }, {
                id : 'lnk-connectivity',
                exec : gui.connectivity.link,
                cleanup: true,
            }, {
                id : 'lnk-deployed_services',
                exec : gui.servicesPools.link,
                cleanup: true,
            }, {
                id : 'lnk-clear_cache',
                exec : gui.clear_cache.link,
                cleanup: false,
            }, {
                id : 'lnk-configuration',
                exec : gui.configuration.link,
                cleanup: false,
            },
        ];
        $.each(sidebarLinks, function(index, value) {
            gui.doLog('Adding ' + value.id);
            $('.' + value.id).unbind('click').click(function(event) {
                event.preventDefault();
                if ($('.navbar-toggle').css('display') != 'none') {
                    $(".navbar-toggle").trigger("click");
                }
                if( value.cleanup ) {
                    gui.cleanup();
                }
                $('html, body').scrollTop(0);
                value.exec(event);
            });
        });
    };

    gui.init = function() {
        // Load jquery validator strings
        $.extend($.validator.messages, {
            required: gettext("This field is required."),
            remote: gettext("Please fix this field."),
            email: gettext("Please enter a valid email address."),
            url: gettext("Please enter a valid URL."),
            date: gettext("Please enter a valid date."),
            dateISO: gettext("Please enter a valid date (ISO)."),
            number: gettext("Please enter a valid number."),
            digits: gettext("Please enter only digits."),
            creditcard: gettext("Please enter a valid credit card number."),
            equalTo: gettext("Please enter the same value again."),
            maxlength: $.validator.format(gettext("Please enter no more than {0} characters.")),
            minlength: $.validator.format(gettext("Please enter at least {0} characters.")),
            rangelength: $.validator.format(gettext("Please enter a value between {0} and {1} characters long.")),
            range: $.validator.format(gettext("Please enter a value between {0} and {1}.")),
            max: $.validator.format(gettext("Please enter a value less than or equal to {0}.")),
            min: $.validator.format(gettext("Please enter a value greater than or equal to {0}."))
        });
        // Set blockui params
        $.blockUI.defaults.baseZ = 2000;

        $.fn.dataTableExt.oSort['uds-date-pre'] = function( s ) {
            return parseInt(s.split('"')[1], 10);
        };
        // Sort for "date" columns (our "dates" are in fact postfix dates rendered as dates with locale format
        $.fn.dataTableExt.oSort['uds-date-asc']  = function(x,y) {
            var val = ((x < y) ? -1 : ((x > y) ?  1 : 0));
            return val;
        };
         
        $.fn.dataTableExt.oSort['uds-date-desc'] = function(x,y) {
            var val = ((x < y) ?  1 : ((x > y) ? -1 : 0));
            return val;
        };        
        // Wait a bit before activating links to give tome tine to initializations
        setTimeout(function(){
            gui.setLinksEvents();
            gui.dashboard.link();
        }, 500);
    };
    
    gui.showDashboard = function() {
        gui.dashboard.link();
    };
    
    // Generic "methods" for editing, creating, etc... 
    
    gui.methods = {};
    
    gui.methods.typedTestButton = function(rest, text, css, type) {
        return [ 
                { 
                    text: text,
                    css: css,
                    action: function(event, form_selector, closeFnc) {
                        var fields = gui.forms.read(form_selector);
                        gui.doLog('Fields: ', fields);
                        rest.test(type, fields, function(data){
                            gui.launchModal(gettext('Test result'), data, { actionButton: ' '});                            
                        }, gui.failRequestModalFnc(gettext('Test error')));
                    },
                }, 
            ];
    };
    
    // "Generic" edit method to set onEdit table
    gui.methods.typedEdit = function(parent, modalTitle, modalErrorMsg, options) {
        options = options || {};
        return function(value, event, table, refreshFnc) {
            gui.tools.blockUI();
            parent.rest.gui(value.type, function(guiDefinition) {
                var buttons = null;
                if( options.testButton ) {
                    buttons = gui.methods.typedTestButton(parent.rest, options.testButton.text, options.testButton.css, value.type);
                }
                var tabs = options.guiProcessor ? options.guiProcessor(guiDefinition) : guiDefinition; // Preprocess fields (probably generate tabs...)
                parent.rest.item(value.id, function(item) {
                    gui.tools.unblockUI();
                    gui.forms.launchModal({
                        title: modalTitle+' <b>'+value.name+'</b>', 
                        fields: tabs, 
                        item: item, 
                        preprocessor: options.preprocessor,
                        buttons: buttons,
                        success: function(form_selector, closeFnc) {
                            var fields = gui.forms.read(form_selector);
                            fields.data_type = value.type;
                            fields = options.fieldsProcessor ? options.fieldsProcessor(fields) : fields; 
                            parent.rest.save(fields, function(data) { // Success on put
                                closeFnc();
                                refreshFnc();
                                gui.notify(gettext('Edition successfully done'), 'success');
                            }, gui.failRequestModalFnc(modalErrorMsg, true)); // Fail on put, show modal message
                       },
                    });
                });
            }, gui.failRequestModalFnc(modalErrorMsg, true));
        };
    };

    // "Generic" new method to set onNew table
    gui.methods.typedNew = function(parent, modalTitle, modalErrorMsg, options) {
        options = options || {};
        return function(type, table, refreshFnc) {
            gui.tools.blockUI();
            parent.rest.gui(type, function(guiDefinition) {
                gui.tools.unblockUI();
                var buttons = null;
                if( options.testButton ) {
                    buttons = gui.methods.typedTestButton(parent.rest, options.testButton.text, options.testButton.css, type);
                }
                var tabs = options.guiProcessor ? options.guiProcessor(guiDefinition) : guiDefinition; // Preprocess fields (probably generate tabs...)
                var title = modalTitle;
                if( parent.types[type] !== undefined ) {
                    title += ' ' + gettext('of type') +' <b>' + parent.types[type].name + '</b>';
                }
                gui.forms.launchModal({
                    title: title, 
                    fields: tabs, 
                    item: undefined, 
                    preprocessor: options.preprocessor,
                    buttons: buttons,
                    success: function(form_selector, closeFnc) {
                        var fields = gui.forms.read(form_selector);
                        if( parent.types[type] !== undefined ) {
                            fields.data_type = type;
                        }
                        fields = options.fieldsProcessor ? options.fieldsProcessor(fields) : fields; // Process fields before creating?
                        parent.rest.create(fields, function(data) { // Success on put
                            closeFnc();
                            refreshFnc();
                            gui.notify(gettext('Creation successfully done'), 'success');
                        }, gui.failRequestModalFnc(modalErrorMsg, true)); // Fail on put, show modal message
                    },
                });
            }, gui.failRequestModalFnc(modalErrorMsg, true));
        };
    };
    
    gui.methods.del = function(parent, modalTitle, modalErrorMsg) {
        return function(value, event, table, refreshFnc) {
            var content = gettext('Are you sure do you want to delete ') + '<b>' + value.name + '</b>';
            var modalId = gui.launchModal(modalTitle, content, { actionButton: '<button type="button" class="btn btn-danger button-accept">' + gettext('Delete') + '</button>'});
            $(modalId + ' .button-accept').click(function(){
                $(modalId).modal('hide');
                parent.rest.del(value.id, function(){
                    refreshFnc();
                    gui.notify(gettext('Item deleted'), 'success');
                }, gui.failRequestModalFnc(modalErrorMsg) );
            });
        };
    };
    
    // Public attributes
    gui.debug = true;
}(window.gui = window.gui || {}, jQuery));
