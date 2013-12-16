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
    var detailLogTable = null;
    var clearDetailLog = function() {
        if( detailLogTable ) {
            var $tbl = $(detailLogTable).dataTable();
            $tbl.fnClearTable();
            $tbl.fnDestroy();
            $('#user-log-placeholder').empty();
            detailLogTable = null;
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
    var searchForm = function(parentModalId, type, id, title, searchLabel, resultsLabel) {
        var errorModal = gui.failRequestModalFnc(gettext('Search error'));
        var srcSelector = parentModalId + ' input[name="name"]';
        
        $(parentModalId + ' .button-search').on('click', function() {
            api.templates.get('search', function(tmpl) { // Get form template
                var modalId = gui.launchModal(title, api.templates.evaluate(tmpl, {
                    search_label : searchLabel,
                    results_label : resultsLabel,
                }), { actionButton: '<button type="button" class="btn btn-success button-accept">' + gettext('Accept') + '</button>'});
                
                var $searchInput = $(modalId + ' input[name="search"]');
                var $select = $(modalId + ' select[name="results"]');
                var $searchButton = $(modalId + ' .button-do-search'); 
                var $saveButton = $(modalId + ' .button-accept'); 
                
                $searchInput.val($(srcSelector).val());
                
                $saveButton.on('click', function(){
                    var value = $select.val();
                    if( value ) {
                        $(srcSelector).val(value);
                        $(modalId).modal('hide');
                    }
                });
                
                $searchButton.on('click', function() {
                    $searchButton.addClass('disabled');
                    var term = $searchInput.val();
                    api.authenticators.search(id, type, term, function(data) {
                        $searchButton.removeClass('disabled');
                        $select.empty();
                        gui.doLog(data);
                        $.each(data, function(undefined, value) {
                            $select.append('<option value="' + value.id + '">' + value.id + ' (' +  value.name + ')</option>');
                        });
                    }, function(jqXHR, textStatus, errorThrown) {
                        $searchButton.removeClass('disabled');
                        errorModal(jqXHR, textStatus, errorThrown);
                    });
                });
                
                $(modalId + ' form').submit(function(event){
                    event.preventDefault();
                    $searchButton.click();
                });
                
                if( $searchInput.val() !== '') {
                    $searchButton.click();
                }
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
                    rowSelect : 'single',
                    buttons : [ 'new', 'edit', 'delete', 'xls' ],
                    onLoad: function(k) {
                        gui.tools.unblockUI();
                    },
                    onEdit: function(value, event, table, refreshFnc) {
                        var exec = function(groups_all) {
                            gui.tools.blockUI();
                            api.templates.get('group', function(tmpl) { // Get form template
                                group.rest.item(value.id, function(item){ // Get item to edit
                                    // Creates modal
                                    var modalId = gui.launchModal(gettext('Edit group') + ' <b>' + item.name + '</b>', api.templates.evaluate(tmpl, {
                                        id: item.id,
                                        type: item.type,
                                        groupname: item.name, 
                                        groupname_label: type.groupNameLabel,
                                        comments: item.comments,
                                        state: item.state,
                                        external: type.isExternal,
                                        canSearchGroups: type.canSearchGroups,
                                        groups: item.groups,
                                        groups_all: groups_all
                                    }));
                                    
                                    gui.tools.applyCustoms(modalId);
                                    gui.tools.unblockUI();
                                    
                                    $(modalId + ' .button-accept').click(function(){
                                        var fields = gui.forms.read(modalId);
                                        gui.doLog('Fields', fields);
                                        group.rest.save(fields, function(data) { // Success on put
                                            $(modalId).modal('hide');
                                            refreshFnc();
                                            gui.notify(gettext('Group saved'), 'success');
                                        }, gui.failRequestModalFnc("Error saving group", true));
                                    });
                                });
                            });
                        };
                        if( value.type == 'meta' ) {
                            // Meta will get all groups
                            group.rest.overview(function(groups) {
                                exec(groups);
                            });
                        } else {
                            exec();
                        }

                    },
                    onNew : function(t, table, refreshFnc) {
                        var exec = function(groups_all) {
                            gui.tools.blockUI();
                            api.templates.get('group', function(tmpl) { // Get form template
                                // Creates modal
                                var modalId = gui.launchModal(gettext('New group'), api.templates.evaluate(tmpl, {
                                    type: t,
                                    groupname_label: type.groupNameLabel,
                                    external: type.isExternal,
                                    canSearchGroups: type.canSearchGroups,
                                    groups: [],
                                    groups_all: groups_all
                                }));
                                gui.tools.unblockUI();
                                
                                gui.tools.applyCustoms(modalId);

                                searchForm(modalId, 'group', id, gettext('Search groups'), gettext('Group'), gettext('Groups found')); // Enable search button click, if it exist ofc
                                
                                $(modalId + ' .button-accept').click(function(){
                                    var fields = gui.forms.read(modalId);
                                    gui.doLog('Fields', fields);
                                    group.rest.create(fields, function(data) { // Success on put
                                        $(modalId).modal('hide');
                                        refreshFnc();
                                        gui.notify(gettext('Group saved'), 'success');
                                    }, gui.failRequestModalFnc("Error saving group", true));
                                });
                            });
                        };
                        if( t == 'meta' ) {
                            // Meta will get all groups
                            group.rest.overview(function(groups) {
                                exec(groups);
                            });
                        } else {
                            exec();
                        }

                    },
                    onDelete: gui.methods.del(group, gettext('Delete group'), gettext('Error deleting group')),
                    
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
                    onRefresh : function() {
                        $('#users-log-placeholder').empty(); // Remove logs on detail refresh
                    },
                    onEdit: function(value, event, table, refreshFnc) {
                        var password = "#æð~¬ŋ@æß”¢€~½¬@#~þ¬@|"; // Garbage for password (to detect change)
                        gui.tools.blockUI();
                        api.templates.get('user', function(tmpl) { // Get form template
                            group.rest.overview(function(groups) { // Get groups
                                user.rest.item(value.id, function(item){ // Get item to edit
                                    
                                    // Creates modal
                                    var modalId = gui.launchModal(gettext('Edit user') + ' <b>' + value.name + '</b>', api.templates.evaluate(tmpl, {
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
                                    
                                    gui.tools.applyCustoms(modalId);
                                    
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
                                var modalId = gui.launchModal(gettext('New user'), api.templates.evaluate(tmpl, {
                                    username_label: type.userNameLabel,
                                    needs_password: type.needsPassword,
                                    password_label: type.passwordLabel,
                                    groups_all: groups,
                                    groups: [],
                                    external: type.isExternal,
                                    canSearchUsers: type.canSearchUsers,
                                }));
                                
                                gui.tools.applyCustoms(modalId);
                                
                                gui.tools.unblockUI();
                                
                                searchForm(modalId, 'user', id, gettext('Search users'), gettext('User'), gettext('Users found')); // Enable search button click, if it exist ofc
                                
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
