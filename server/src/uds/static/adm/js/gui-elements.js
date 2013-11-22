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
    gui.clearWorkspace();
    gui.appendToWorkspace(gui.breadcrumbs(gettext('Service Providers')));

    var tableId = gui.providers.table({
        rowSelect : 'single',
        onEdit: function(value, event, table) {
            gui.providers.rest.gui(value.type, function(data) {
                   var form = gui.fields(data);
                   gui.appendToWorkspace(gui.modal('edit_modal', gettext('Edit service provider'), form));
                   $('#edit_modal').modal()
                       .on('hidden.bs.modal', function () {
                           $('#edit_modal').remove();
                       });
               });
        },
        buttons : [ 'edit', 'delete', 'xls' ],
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
            buttons : [ 'edit', 'delete', 'xls' ],
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
                    scrollToTable : true,
                    onLoad: function(k) {
                        api.tools.unblockUI();
                    },
                });
                return false;
            },
            onRefresh : function() {
                $('#users-placeholder').empty(); // Remove detail on parent refresh
            },
            onEdit: function(value, event, table) {
                gui.authenticators.rest.gui(value.type, function(data){
                       var form = gui.fields(data);
                       gui.launchModal(gettext('Edit authenticator')+' '+value.name, form);
                   });
            },
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
            rowSelect : 'multi',
            container : 'transports-placeholder',
            buttons : [ 'new', 'edit', 'delete', 'xls' ],
            onEdit: function(value, event, table) {
                gui.connectivity.transports.rest.gui(value.type, function(itemGui){
                       gui.connectivity.transports.rest.item(value.id, function(item) {
                               var form = gui.fields(itemGui, item);
                               gui.launchModal(gettext('Edit transport')+' '+value.name,form, function(form_selector) {
                                   var fields = gui.fields.read(form_selector);
                                   return false;
                               });
                           });
                   });
            },
            onNew: function(type) {
                gui.doLog(type);
            },
        });
        gui.connectivity.networks.table({
            rowSelect : 'multi',
            container : 'networks-placeholder',
            buttons : [ 'new', 'edit', 'delete', 'xls' ],
        });
    });
      
};
