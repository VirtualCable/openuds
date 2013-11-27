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

    gui.modal = function(id, title, content, actionButton, closeButton) {
        return api.templates.evaluate('tmpl_modal', {
            id: id,
            title: title,
            content: content,
            button1: closeButton,
            button2: actionButton
        });
    };
    
    gui.launchModal = function(title, content, actionButton, closeButton) {
        var id = Math.random().toString().split('.')[1]; // Get a random ID for this modal
        gui.appendToWorkspace(gui.modal(id, title, content, actionButton, closeButton));
        id = '#' + id; // for jQuery
        
        $(id).modal()
        .on('hidden.bs.modal', function () {
            $(id).remove();
        });
    };
    
    gui.launchModalForm = function(title, form, onSuccess) {
        var id = 'modal-' + Math.random().toString().split('.')[1]; // Get a random ID for this modal
        gui.appendToWorkspace(gui.modal(id, title, form));
        id = '#' + id; // for jQuery
        
        // Get form
        var $form = $(id + ' form'); 
        
        // For "beauty" switches, initialize them now
        $(id + ' .make-switch').bootstrapSwitch();
        // Activate "cool" selects
        $(id + ' .selectpicker').selectpicker();
        // TEST: cooller on mobile devices
        if( /Android|webOS|iPhone|iPad|iPod|BlackBerry/i.test(navigator.userAgent) ) {
            $(id + ' .selectpicker').selectpicker('mobile');
        }
        // Activate tooltips
        $(id + ' [data-toggle="tooltip"]').tooltip({delay: {show: 1000, hide: 100}, placement: 'auto right'});
        
        // Validation
        $form.validate({
            debug: true,
            errorClass: 'text-danger',
            validClass: 'has-success',
            highlight: function(element) {
                $(element).closest('.form-group').addClass('has-error');
            },
            success: function(element) {
                $(element).closest('.form-group').removeClass('has-error');
                $(element).remove();
            },
        }); 
        
        // And catch "accept" (default is "Save" in fact) button click
        $(id + ' .button-accept').click(function(){
            if( !$form.valid() )
                return;
            if( onSuccess ) {
                onSuccess(id + ' form', function(){$(id).modal('hide');}); // Delegate close to to onSuccess  
                    return;
            } else {
                $(id).modal('hide');
            }
            
        });
        
        // Launch modal
        $(id).modal({keyboard: false})
             .on('hidden.bs.modal', function () {
                 $(id).remove();
             });
    };
    
    gui.failRequestMessageFnc = function(jqXHR, textStatus, errorThrown) {
        api.templates.get('request_failed', function(tmpl) {
            gui.clearWorkspace();
            gui.appendToWorkspace(api.templates.evaluate(tmpl, {
                error: jqXHR.responseText,
            }));            
        });
        gui.setLinksEvents();
    };
    
    gui.failRequestModalFnc = function(title) {
        return function(jqXHR, textStatus, errorThrown) { // fail on put
            gui.launchModal(title, jqXHR.responseText, ' ');
        };
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
        
        gui.setLinksEvents();
        gui.dashboard.link();
    };

    // Public attributes
    gui.debug = true;
}(window.gui = window.gui || {}, jQuery));

