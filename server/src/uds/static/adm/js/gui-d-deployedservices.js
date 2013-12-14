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

        var testClick = function(val, value, btn, tbl, refreshFnc) {
            gui.doLog(value);
        };
        var counter = 0;
        var testSelect = function(val, value, btn, tbl, refreshFnc) {
            if( !val ) {
                $(btn).removeClass('btn3d-info').addClass('disabled');
                return;
            }
            $(btn).removeClass('disabled').addClass('btn3d-info');
            counter = counter + 1;
            gui.doLog('Select', counter.toString(), val, value);
        };
        
        var tableId = gui.deployedservices.table({
            container : 'deployed-services-placeholder',
            rowSelect : 'single',
            buttons : [ 'new', 'edit', 'delete', { text: gettext('Test'), css: 'disabled', click: testClick, select: testSelect }, 'xls' ],
            onData: function(data) {
                gui.doLog(data);
            }
        });
    });

      
};
