//------------------------
// Os managers
//------------------------
gui.osmanagers = new GuiElement(api.osmanagers, 'osm');
gui.osmanagers.link = function(event) {
    "use strict";
    // Cleans up memory used by other datatables
    $.each($.fn.dataTable.fnTables(), function(undefined, tbl){
        $(tbl).dataTable().fnDestroy();
    });
    gui.clearWorkspace();
    gui.appendToWorkspace(gui.breadcrumbs('Os Managers'));

    gui.osmanagers.table({
        rowSelect : 'single',
        buttons : [ 'new', 'edit', 'delete', 'xls' ],
        onNew : gui.methods.typedNew(gui.osmanagers, gettext('New OSManager'), gettext('Error creating OSManager')),
        onEdit: gui.methods.typedEdit(gui.osmanagers, gettext('Edit OSManager'), gettext('Error processing OSManager')),
        onDelete: gui.methods.del(gui.osmanagers, gettext('Delete OSManager'), gettext('Error deleting OSManager')),
    });

    return false;
};
