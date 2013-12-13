/* jshint strict: true */
gui.deployedservices = new GuiElement(api.deployedservices, 'deployedservices');
 

gui.deployedservices.link = function(event) {
    "use strict";
    
    api.templates.get('deployedservices', function(tmpl) {
        gui.clearWorkspace();
        gui.appendToWorkspace(api.templates.evaluate(tmpl, {
            deployed_services : 'deployed-services-placeholder',
        }));
        gui.setLinksEvents();

        var tableId = gui.deployedservices.table({
            container : 'deployed-services-placeholder',
            rowSelect : 'single',
            buttons : [ 'new', 'edit', 'delete', 'xls' ],
        });
    });

      
};
