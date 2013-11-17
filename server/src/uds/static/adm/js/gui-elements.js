// Compose gui elements

// Service providers
gui.providers = new GuiElement(api.providers, 'provi');
gui.providers.link = function(event) {
    gui.clearWorkspace();
    gui.appendToWorkspace(gui.breadcrumbs(gettext('Service Providers')));

    var tableId = gui.providers.table({
        rowSelect : 'multi',
        rowSelectFnc : function(nodes) {
            gui.doLog(nodes);
            gui.doLog(this);
            gui.doLog(this.fnGetSelectedData());
        },
        buttons : [ 'edit', 'refresh', 'delete' ],
    });

    return false;
};

// --------------..
// Authenticators
// ---------------
gui.authenticators = new GuiElement(api.authenticators, 'auth');

gui.authenticators.link = function(event) {
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
            buttons : [ 'edit', 'refresh', 'delete' ],
            onRowSelect : function(nodes) {
                var id = this.fnGetSelectedData()[0].id;
                var user = new GuiElement(api.authenticators.users.detail(id), 'users');
                user.table({
                    container : 'users-placeholder',
                    rowSelect : 'multi',
                    buttons : [ 'edit', 'refresh', 'delete' ],
                    scroll : true,
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
    gui.clearWorkspace();
    gui.appendToWorkspace(gui.breadcrumbs('Os Managers'));

    gui.osmanagers.table({
        rowSelect : 'single',
        buttons : [ 'edit', 'refresh', 'delete' ],
    });

    return false;
};

gui.connectivity = {
    transports : new GuiElement(api.transports, 'trans'),
    networks : new GuiElement(api.networks, 'nets'),
};

gui.connectivity.link = function(event) {
    gui.clearWorkspace();
    gui.appendToWorkspace(gui.breadcrumbs(gettext('Connectivity')));
    gui
            .appendToWorkspace('<div class="row"><div class="col-lg-6" id="ttbl"></div><div class="col-lg-6" id="ntbl"></div></div>');

    gui.connectivity.transports.table({
        rowSelect : 'multi',
        container : 'ttbl',
        buttons : [ 'edit', 'refresh', 'delete', 'pdf' ],
    });
    gui.connectivity.networks.table({
        rowSelect : 'multi',
        container : 'ntbl',
        buttons : [ 'edit', 'refresh', 'delete' ],
    });
};
