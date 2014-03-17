/* jshint strict: true */

// Basic GUI components

// Tools
gui.clear_cache = new BasicGuiElement('Flush cache');
gui.clear_cache.link = function() {
    "use strict";
    api.getJson('cache/flush', {
        success: function() { 
            gui.launchModal(gettext('Cache'), gettext('Cache has been flushed'), { actionButton: ' ' } ); 
        },
    });
    
};