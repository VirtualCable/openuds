/* jshint strict: true */
// Compose gui elements

gui.dashboard = new BasicGuiElement('Dashboard');
gui.dashboard.link = function(event) {
    "use strict";
    gui.clearWorkspace();
    api.templates.get('dashboard', function(tmpl) {
        gui.doLog('enter dashboard');
        gui.appendToWorkspace(api.templates.evaluate(tmpl, {
        }));
        gui.setLinksEvents();
        
        $.each($('.btn3d'), function() {
           console.log(this); 
           var counter = 0;
           $(this).click(function(){
               counter += 1;
               $(this).text($(this).text().split(' ')[0] + ' ' + counter);
               /*$('<span>Click ' + counter + ' on ' + $(this).text() + '<b>--</b></span>').appendTo('#out');*/
           });
        });
        
        api.tools.fix3dButtons('#test');
    });
};

// Service providers
gui.providers = new GuiElement(api.providers, 'provi');
gui.providers.link = function(event) {
    "use strict";
    api.templates.get('providers', function(tmpl) {
        gui.clearWorkspace();
        gui.appendToWorkspace(api.templates.evaluate(tmpl, {
            providers : 'providers-placeholder',
            services : 'services-placeholder',
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
            onRowSelect : function(selected) {
                api.tools.blockUI();
                gui.doLog(selected[0]);
                var id = selected[0].id;
                // Giving the name compossed with type, will ensure that only styles will be reattached once
                var services = new GuiElement(api.providers.detail(id, 'services'), 'services-'+selected[0].type);
                
                services.table({
                    container : 'services-placeholder',
                    rowSelect : 'single',
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
                    onEdit : gui.methods.typedEdit(services, gettext('Edit service'), gettext('Error processing service')),
                    onNew : gui.methods.typedNew(services, gettext('New service'), gettext('Error creating service')),
                    onDelete: gui.methods.del(services, gettext('Delete service'), gettext('Error deleting service')),
                    scrollToTable : false,
                    onLoad: function(k) {
                        api.tools.unblockUI();
                    },
                });
                return false;
            },
            buttons : [ 'new', 'edit', 'delete', 'xls' ],
            onNew : gui.methods.typedNew(gui.providers, gettext('New provider'), gettext('Error creating provider')),
            onEdit: gui.methods.typedEdit(gui.providers, gettext('Edit provider'), gettext('Error processing provider')),
            onDelete: gui.methods.del(gui.providers, gettext('Delete provider'), gettext('Error deleting provider')),
        });
    });

    return false;
};

// --------------..
// Authenticators
// ---------------
gui.authenticators = new GuiElement(api.authenticators, 'auth');

gui.authenticators.link = function(event) {
    "use strict";
    gui.doLog('enter auths');
    api.templates.get('authenticators', function(tmpl) {
        gui.clearWorkspace();
        gui.appendToWorkspace(api.templates.evaluate(tmpl, {
            auths : 'auths-placeholder',
            users : 'users-placeholder',
            groups: 'groups-placeholder',
        }));
        gui.setLinksEvents();

        gui.authenticators.table({
            container : 'auths-placeholder',
            rowSelect : 'single',
            buttons : [ 'new', 'edit', 'delete', 'xls' ],
            onRowSelect : function(selected) {
                api.tools.blockUI();
                var id = selected[0].id;
                var user = new GuiElement(api.authenticators.detail(id, 'users'), 'users');
                var group = new GuiElement(api.authenticators.detail(id, 'groups'), 'groups');
                group.table({
                    container : 'groups-placeholder',
                    rowSelect : 'multi',
                    buttons : [ 'edit', 'delete', 'xls' ],
                    onLoad: function(k) {
                        api.tools.unblockUI();
                    },
                });
                user.table({
                    container : 'users-placeholder',
                    rowSelect : 'multi',
                    buttons : [ 'new', 'edit', 'delete', 'xls' ],
                    scrollToTable : false,
                    onLoad: function(k) {
                        api.tools.unblockUI();
                    },
                });
                return false;
            },
            onRefresh : function() {
                $('#users-placeholder').empty(); // Remove detail on parent refresh
            },
            onNew : gui.methods.typedNew(gui.authenticators, gettext('New authenticator'), gettext('Error creating authenticator')),
            onEdit: gui.methods.typedEdit(gui.authenticators, gettext('Edit authenticator'), gettext('Error processing authenticator')),
            onDelete: gui.methods.del(gui.authenticators, gettext('Delete authenticator'), gettext('Error deleting authenticator')),
            
        });
    });

    return false;
};

gui.osmanagers = new GuiElement(api.osmanagers, 'osm');
gui.osmanagers.link = function(event) {
    "use strict";
    gui.clearWorkspace();
    gui.appendToWorkspace(gui.breadcrumbs('Os Managers'));

    gui.osmanagers.table({
        rowSelect : 'single',
        buttons : [ 'edit', 'delete', 'xls' ],
    });

    return false;
};

gui.connectivity = {
    transports : new GuiElement(api.transports, 'trans'),
    networks : new GuiElement(api.networks, 'nets'),
};

gui.connectivity.link = function(event) {
    "use strict";
    api.templates.get('connectivity', function(tmpl) {
        gui.clearWorkspace();
        gui.appendToWorkspace(api.templates.evaluate(tmpl, {
            transports : 'transports-placeholder',
            networks : 'networks-placeholder'
        }));

        gui.connectivity.transports.table({
            rowSelect : 'single',
            container : 'transports-placeholder',
            buttons : [ 'new', 'edit', 'delete', 'xls' ],
            onEdit: function(value, event, table, refreshFnc) {
                gui.connectivity.transports.rest.gui(value.type, function(itemGui){
                       gui.connectivity.transports.rest.item(value.id, function(item) {
                           var tabs = { 
                                   tabs: [
                                      {
                                       title: 'General',
                                       fields: itemGui,
                                      },
                                      {
                                       title: 'Networks',
                                       fields: [],
                                      },
                                   ]
                               };
                           gui.forms.launchModal(gettext('Edit transport')+' '+value.name, tabs, item, function(form_selector, closeFnc) {
                               var fields = gui.forms.read(form_selector);
                               fields.data_type = value.type;
                               fields.nets_positive = false;
                               gui.connectivity.transports.rest.save(fields, function(data) { // Success on put
                                   closeFnc();
                                   refreshFnc();
                               }, gui.failRequestModalFnc(gettext('Error creating transport')) // Fail on put, show modal message
                               );
                               return false;
                           });
                       });
                   });
            },
            onNew: function(type, table, refreshFnc) {
                gui.connectivity.transports.rest.gui(type, function(itemGui) {
                    var tabs = { 
                        tabs: [
                           {
                            title: 'General',
                            fields: itemGui,
                           },
                           {
                            title: 'Networks',
                            fields: [
                                gui.forms.guiField('networks', 'multichoice', gettext('Available for networks'), 
                                        gettext('Select networks that will see this transport'), [], []),
                                gui.forms.guiField('nets_positive', 'checkbox', gettext('Transport active for selected networks'),
                                        gettext('If active, transport will only be available on selected networks. If inactive, transport will be available form any net EXCEPT selected networks'),
                                        true) 
                            ],
                           },
                        ]
                    };
                    gui.forms.launchModal(gettext('New transport'), tabs, undefined, function(form_selector, closeFnc) {
                        var fields = gui.form.read(form_selector);
                        // Append "own" fields, in this case data_type
                        fields.data_type = type;
                        fields.nets_positive = false;
                        gui.connectivity.transports.rest.create(fields, function(data) { // Success on put
                            closeFnc();
                            refreshFnc();
                        }, gui.failRequestModalFnc(gettext('Error creating transport')) // Fail on put, show modal message
                        );
                    });
                });
            },
            onDelete: function(value, event, table, refreshFncs) {
                // TODO: Add confirmation to deletion
                gui.connectivity.transports.rest.del(value.id, function(){
                    refreshFnc();
                }, gui.failRequestModalFnc(gettext('Error removing transport')) );
            },
        });
        gui.connectivity.networks.table({
            rowSelect : 'multi',
            container : 'networks-placeholder',
            buttons : [ 'new', 'edit', 'delete', 'xls' ],
        });
    });
      
};

// Tools
gui.clear_cache = new BasicGuiElement('Clear cache');
gui.clear_cache.link = function() {
    "use strict";
    api.getJson('cache/flush', {
        success: function() { 
            gui.launchModal(gettext('Cache'), gettext('Cache has been flushed'), ' ' ); 
        },
    });
    
};