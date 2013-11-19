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
        rowSelect : 'multi',
        rowSelectFnc : function(nodes) {
            gui.doLog(nodes);
            gui.doLog(this);
            gui.doLog(this.fnGetSelectedData());
        },
        buttons : [ 'edit', 'refresh', 'delete', 'xls' ],
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
            users : 'users-placeholder'
        }));
        gui.setLinksEvents();

        gui.authenticators.table({
            container : 'auths-placeholder',
            rowSelect : 'single',
            buttons : [ 'edit', 'refresh', 'delete', 'xls' ],
            onRowSelect : function(nodes) {
                api.tools.blockUI();
                var id = this.fnGetSelectedData()[0].id;
                var user = new GuiElement(api.authenticators.detail(id, 'users'), 'users');
                user.table({
                    container : 'users-placeholder',
                    rowSelect : 'multi',
                    buttons : [ 'edit', 'refresh', 'delete', 'xls' ],
                    scroll : true,
                    onLoad: function(k) {
                        api.tools.unblockUI();
                    },
                });
                return false;
            },
            onRefresh : function() {
                $('#users-placeholder').empty(); // Remove detail on parent refresh
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
        buttons : [ 'edit', 'refresh', 'delete', 'xls' ],
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
            buttons : [ 'edit', 'refresh', 'delete', 'xls' ],
        });
        gui.connectivity.networks.table({
            rowSelect : 'multi',
            container : 'networks-placeholder',
            buttons : [ 'edit', 'refresh', 'delete', 'xls' ],
        });
    });
      
};
