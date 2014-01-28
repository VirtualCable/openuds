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
            
            var d1 = [];
            for (var i = 0; i < 14; i += 0.5) {
                    d1.push([i, Math.sin(i)]);
            }

            var d2 = [[0, 3], [4, 8], [8, 5], [9, 13]];

            // A null signifies separate line segments

            var d3 = [[0, 12], [7, 12], null, [7, 2.5], [12, 2.5]];

            $.plot("#placeholder", [ d1, d2, d3 ]);            
        });
        
        gui.tools.fix3dButtons('#test');
    });
};
