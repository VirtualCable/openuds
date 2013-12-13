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
    });

      
};
