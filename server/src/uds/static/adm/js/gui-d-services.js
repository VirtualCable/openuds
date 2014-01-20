/* jshint strict: true */
gui.providers = new GuiElement(api.providers, 'provi');
gui.providers.link = function(event) {
    "use strict";

    // Button definition to trigger "Test" action
    var testButton = {
            testButton: {
                text: gettext('Test'),
                css: 'btn-info',
            },
    };
    
    var detailLogTable = null;
    var clearDetailLog = function() {
        if( detailLogTable ) {
            var $tbl = $(detailLogTable).dataTable();
            $tbl.fnClearTable();
            $tbl.fnDestroy();
            $('#services-log-placeholder').empty();
            detailLogTable = undefined;
        }
    };
    
    var prevTables = [];
    var clearDetails = function() {
        gui.doLog('Clearing details');
        $.each(prevTables, function(undefined, tbl){
            var $tbl = $(tbl).dataTable();
            $tbl.fnClearTable();
            $tbl.fnDestroy();
        });
        
        clearDetailLog();
        
        prevTables = [];
        $('#services-placeholder').empty();
        $('#logs-placeholder').empty();
        
        $('#detail-placeholder').addClass('hidden');
    };

    api.templates.get('providers', function(tmpl) {
        gui.clearWorkspace();
        gui.appendToWorkspace(api.templates.evaluate(tmpl, {
            providers : 'providers-placeholder',
            services : 'services-placeholder',
            services_log : 'services-log-placeholder',
            logs:   'logs-placeholder',
        }));
        gui.setLinksEvents();
    
        var tableId = gui.providers.table({
            container : 'providers-placeholder',
            rowSelect : 'single',
            onCheck : function(check, items) { // Check if item can be deleted
                /*if( check == 'delete' ) {
                    for( var i in items ) {
                        if( items[i].services_count > 0)
                            return false;
                    }
                    return true;
                }*/
                return true;
            },
            onRowDeselect: function() {
                clearDetails();
            },
            onRowSelect : function(selected) {
                gui.tools.blockUI();
                
                clearDetails();
                $('#detail-placeholder').removeClass('hidden');
                
                var id = selected[0].id;
                // Giving the name compossed with type, will ensure that only styles will be reattached once
                var services = new GuiElement(api.providers.detail(id, 'services'), 'services-'+selected[0].type);
                
                var tmpLogTable = null;
                var servicesTable = services.table({
                    container : 'services-placeholder',
                    rowSelect : 'single',
                    onRowSelect: function(sselected) {
                        gui.tools.blockUI();
                        var sId = sselected[0].id;
                        
                        clearDetailLog();
                        
                        tmpLogTable = services.logTable(sId, {
                            container: 'services-log-placeholder',
                            onLoad: function() {
                                detailLogTable = tmpLogTable;
                                gui.tools.unblockUI();
                            }
                        });
                    },
                    onRowDeselect : function() {
                        clearDetailLog();
                    },
                    onCheck: function(check, items) {
                        if( check == 'delete' ) {
                            for( var i in items ) {
                                if( items[i].deployed_services_count > 0)
                                    return false;
                            }
                            return true;
                        }
                        return true;
                    },
                    buttons : [ 'new', 'edit', 'delete', 'xls' ],
                    onEdit : gui.methods.typedEdit(services, gettext('Edit service'), gettext('Error processing service'), testButton),
                    onNew : gui.methods.typedNew(services, gettext('New service'), gettext('Error creating service'), testButton),
                    onDelete: gui.methods.del(services, gettext('Delete service'), gettext('Error deleting service'), testButton),
                    scrollToTable : false,
                    onLoad: function(k) {
                        gui.tools.unblockUI();
                    },
                });
                
                var logTable = gui.providers.logTable(id, {
                    container : 'logs-placeholder',
                });
                
                prevTables.push(servicesTable);
                prevTables.push(logTable);
            },
            buttons : [ 'new', 'edit', 'delete', 'xls' ],
            onNew : gui.methods.typedNew(gui.providers, gettext('New provider'), gettext('Error creating provider'), testButton),
            onEdit: gui.methods.typedEdit(gui.providers, gettext('Edit provider'), gettext('Error processing provider'), testButton),
            onDelete: gui.methods.del(gui.providers, gettext('Delete provider'), gettext('Error deleting provider')),
        });
    });

    return false;
};
