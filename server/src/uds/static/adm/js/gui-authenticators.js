/* jshint strict: true */
gui.authenticators = new GuiElement(api.authenticators, 'auth');

gui.authenticators.link = function(event) {
    "use strict";

    // Button definition to trigger "Test" action
    var testButton = {
            testButton: {
                text: gettext('Test authenticator'),
                css: 'btn-info',
            },
    };
    
    var detailLogTable;
    var clearDetailLog = function() {
        if( detailLogTable ) {
            var $tbl = $(detailLogTable).dataTable();
            $tbl.fnClearTable();
            $tbl.fnDestroy();
            $('#user-log-placeholder').empty();
            detailLogTable = undefined;
        }
    };
    
    var prevTables = [];
    var clearDetails = function() {
        $.each(prevTables, function(undefined, tbl){
            var $tbl = $(tbl).dataTable();
            $tbl.fnClearTable();
            $tbl.fnDestroy();
        });
        
        clearDetailLog();

        $('#users-placeholder').empty();
        $('#groups-placeholder').empty();
        $('#logs-placeholder').empty();
        
        $('#detail-placeholder').addClass('hidden');
        
        prevTables = [];
    };
    
    gui.doLog('enter auths');
    api.templates.get('authenticators', function(tmpl) {
        gui.clearWorkspace();
        gui.appendToWorkspace(api.templates.evaluate(tmpl, {
            auths : 'auths-placeholder',
            users : 'users-placeholder',
            users_log : 'users-log-placeholder',
            groups: 'groups-placeholder',
            logs:   'logs-placeholder',
        }));
        gui.setLinksEvents();

        var tableId = gui.authenticators.table({
            container : 'auths-placeholder',
            rowSelect : 'single',
            buttons : [ 'new', 'edit', 'delete', 'xls' ],
            onRowDeselect: function() {
                clearDetails();
            },
            onRowSelect : function(selected) {
                
                // We can have lots of users, so memory can grow up rapidly if we do not keep thins clena
                // To do so, we empty previous table contents before storing new table contents
                // Anyway, TabletTools will keep "leaking" memory, but we can handle a little "leak" that will be fixed as soon as we change the section
                clearDetails();
                $('#detail-placeholder').removeClass('hidden');
                
                gui.tools.blockUI();
                var id = selected[0].id;
                var user = new GuiElement(api.authenticators.detail(id, 'users'), 'users');
                var group = new GuiElement(api.authenticators.detail(id, 'groups'), 'groups');
                var grpTable = group.table({
                    container : 'groups-placeholder',
                    rowSelect : 'multi',
                    buttons : [ 'edit', 'delete', 'xls' ],
                    onLoad: function(k) {
                        gui.tools.unblockUI();
                    },
                });
                var tmpLogTable;
                // Use defered rendering for users, this table can be "huge"
                var usrTable = user.table({
                    container : 'users-placeholder',
                    rowSelect : 'single',
                    onRowSelect: function(uselected) {
                        gui.tools.blockUI();
                        var uId = uselected[0].id;
                        
                        clearDetailLog();
                        
                        tmpLogTable = user.logTable(uId, {
                            container: 'users-log-placeholder',
                            onLoad: function() {
                                detailLogTable = tmpLogTable;
                                gui.tools.unblockUI();
                            }
                        });
                    },
                    onRowDeselect : function() {
                        clearDetailLog();
                    },
                    buttons : [ 'new', 'edit', 'delete', 'xls' ],
                    deferedRender: true,
                    scrollToTable : false,
                    onLoad: function(k) {
                        gui.tools.unblockUI();
                    },
                });
                
                var logTable = gui.authenticators.logTable(id, {
                    container : 'logs-placeholder',
                });
                
                // So we can destroy the tables beforing adding new ones
                prevTables.push(grpTable);
                prevTables.push(usrTable);
                prevTables.push(logTable);
                
                return false;
            },
            onRefresh : function() {
                $('#users-placeholder').empty(); // Remove detail on parent refresh
            },
            onNew : gui.methods.typedNew(gui.authenticators, gettext('New authenticator'), gettext('Error creating authenticator'),testButton),
            onEdit: gui.methods.typedEdit(gui.authenticators, gettext('Edit authenticator'), gettext('Error processing authenticator'), testButton),
            onDelete: gui.methods.del(gui.authenticators, gettext('Delete authenticator'), gettext('Error deleting authenticator')),
            
        });
    });

    return false;
};
