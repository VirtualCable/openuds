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
    
    // Clears the log of the detail, in this case, the log of "users"
    // Memory saver :-)
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
    
    // Clears the details
    // Memory saver :-)
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
    
    
    // Search button event generator for user/group
    var searchForm = function(modalId, model, title, searchLabel, resultsLabel, srcSelector) {
        $(modalId + ' .button-search').on('click', function() {
            api.templates.get('search', function(tmpl) { // Get form template
                var modalId = gui.launchModal(title, api.templates.evaluate(tmpl, {
                    search_label : searchLabel,
                    results_label : resultsLabel,
                }), { actionButton: '<button type="button" class="btn btn-success button-accept">' + gettext('Accept') + '</button>'});
                var searchInput = modalId + ' input[name="search"]';
                var resultsInput = modalId + ' select';
                
                $(searchInput).val($(srcSelector).val());
                
                $(modalId + ' .button-accept').on('click', function(){
                    gui.doLog('Accepted'); 
                });
                
            });
        });  
    };
    
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
                var type = gui.authenticators.types[selected[0].type];
                gui.doLog('Type', type);
                
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
                
                // New button will only be shown on authenticators that can create new users
                var usrButtons = ['edit', 'delete', 'xls'];
                if( type.canCreateUsers ) {
                    usrButtons = ['new'].concat(usrButtons); // New is first button
                }
                
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
                    buttons : usrButtons,
                    deferedRender: true,    // Use defered rendering for users, this table can be "huge"
                    scrollToTable : false,
                    onLoad: function(k) {
                        gui.tools.unblockUI();
                    },
                    onEdit: function(value, event, table, refreshFnc) {
                        var password = "#æð~¬~@æß”¢ß€~½¬@#~½¬@|"; // Garbage for password (to detect change)
                        gui.tools.blockUI();
                        api.templates.get('user', function(tmpl) { // Get form template
                            group.rest.overview(function(groups) { // Get groups
                                user.rest.item(value.id, function(item){ // Get item to edit
                                    
                                    // Creates modal
                                    var modalId = gui.launchModal(gettext('Edit user'), api.templates.evaluate(tmpl, {
                                        id: item.id,
                                        username: item.name, 
                                        username_label: type.userNameLabel,
                                        realname: item.real_name,
                                        comments: item.comments,
                                        state: item.state,
                                        staff_member: item.staff_member,
                                        is_admin: item.is_admin,
                                        needs_password: type.needsPassword,
                                        password: type.needsPassword ? password : undefined,
                                        password_label: type.passwordLabel,
                                        groups_all: groups,
                                        groups: item.groups,
                                        external: type.isExternal,
                                        canSearchUsers: type.canSearchUsers,
                                    }));
                                    
                                    // Activate "custom" styles
                                    $(modalId + ' .make-switch').bootstrapSwitch();
                                    // Activate "cool" selects
                                    $(modalId + ' .selectpicker').selectpicker();
                                    // TEST: cooler on mobile devices
                                    if( /Android|webOS|iPhone|iPad|iPod|BlackBerry/i.test(navigator.userAgent) ) {
                                        $(modalId + ' .selectpicker').selectpicker('mobile');
                                    }
                                    // Activate tooltips
                                    $(modalId + ' [data-toggle="tooltip"]').tooltip({delay: {show: 1000, hide: 100}, placement: 'auto right'});
                                    
                                    gui.tools.unblockUI();
                                    
                                    $(modalId + ' .button-accept').click(function(){
                                        var fields = gui.forms.read(modalId);
                                        // If needs password, and password has changed
                                        if( type.needsPassword ) {
                                            if( fields.password == password)
                                                delete fields.password;
                                        }
                                        gui.doLog('Fields', fields);
                                        user.rest.save(fields, function(data) { // Success on put
                                            $(modalId).modal('hide');
                                            refreshFnc();
                                            gui.notify(gettext('User saved'), 'success');
                                        }, gui.failRequestModalFnc("Error saving user", true));
                                    });
                                });
                            });
                        });
                    },
                    onNew: function(undefined, table, refreshFnc) {
                        gui.tools.blockUI();
                        api.templates.get('user', function(tmpl) { // Get form template
                            group.rest.overview(function(groups) { // Get groups
                                // Creates modal
                                var modalId = gui.launchModal(gettext('Edit user'), api.templates.evaluate(tmpl, {
                                    username_label: type.userNameLabel,
                                    needs_password: type.needsPassword,
                                    password_label: type.passwordLabel,
                                    groups_all: groups,
                                    groups: [],
                                    external: type.isExternal,
                                    canSearchUsers: type.canSearchUsers,
                                }));
                                
                                // Activate "custom" styles
                                $(modalId + ' .make-switch').bootstrapSwitch();
                                // Activate "cool" selects
                                $(modalId + ' .selectpicker').selectpicker();
                                // TEST: cooler on mobile devices
                                if( /Android|webOS|iPhone|iPad|iPod|BlackBerry/i.test(navigator.userAgent) ) {
                                    $(modalId + ' .selectpicker').selectpicker('mobile');
                                }
                                // Activate tooltips
                                $(modalId + ' [data-toggle="tooltip"]').tooltip({delay: {show: 1000, hide: 100}, placement: 'auto right'});
                                
                                gui.tools.unblockUI();
                                
                                searchForm(modalId, user, gettext('Search users'), gettext('User'), gettext('Users found'), modalId + ' input[name="name"]'); // Enable search button click, if it exist ofc
                                
                                $(modalId + ' .button-accept').click(function(){
                                    var fields = gui.forms.read(modalId);
                                    // If needs password, and password has changed
                                    gui.doLog('Fields', fields);
                                    user.rest.create(fields, function(data) { // Success on put
                                        $(modalId).modal('hide');
                                        refreshFnc();
                                        gui.notify(gettext('User saved'), 'success');
                                    }, gui.failRequestModalFnc("Error saving user", true));
                                });
                            });
                        });
                    },
                    onDelete: gui.methods.del(user, gettext('Delete user'), gettext('Error deleting user')),
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
