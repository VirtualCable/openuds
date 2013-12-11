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
        
        gui.tools.fix3dButtons('#test');
    });
};

// Tools
gui.clear_cache = new BasicGuiElement('Clear cache');
gui.clear_cache.link = function() {
    "use strict";
    api.getJson('cache/flush', {
        success: function() { 
            gui.launchModal(gettext('Cache'), gettext('Cache has been flushed'), { actionButton: ' ' } ); 
        },
    });
    
};