/* jshint strict: true */
gui.connectivity = {
    transports : new GuiElement(api.transports, 'trans'),
    networks : new GuiElement(api.networks, 'nets'),
};

gui.connectivity.link = function(event) {
    "use strict";
    // Cleans up memory used by other datatables
    $.each($.fn.dataTable.fnTables(), function(undefined, tbl){
        $(tbl).dataTable().fnDestroy();
    });
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
            onNew : gui.methods.typedNew(gui.connectivity.transports, gettext('New transport'), gettext('Error creating transport')),
            onEdit: gui.methods.typedEdit(gui.connectivity.transports, gettext('Edit transport'), gettext('Error processing transport')),
            onDelete: gui.methods.del(gui.connectivity.transports, gettext('Delete transport'), gettext('Error deleting transport')),
        });
        gui.connectivity.networks.table({
            rowSelect : 'multi',
            container : 'networks-placeholder',
            buttons : [ 'new', 'edit', 'delete', 'xls' ],
        });
    });
      
};