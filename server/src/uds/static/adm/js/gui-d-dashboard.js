gui.dashboard = new BasicGuiElement('Dashboard');
gui.dashboard.link = function(event) {
    "use strict";
    gui.clearWorkspace();
    api.templates.get('dashboard', function(tmpl) {
        api.system.overview(function(data){
            
            gui.doLog('enter dashboard');
            gui.appendToWorkspace(api.templates.evaluate(tmpl, {
                users: data.users,
                services: data.services,
                user_services: data.user_services,
                restrained_services_pools: data.restrained_services_pools,
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
        });
        
        gui.tools.fix3dButtons('#test');
    });
};
