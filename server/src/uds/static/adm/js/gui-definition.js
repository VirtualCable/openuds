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
            onEdit: function(value, event, table, refreshFnc) {
                gui.connectivity.transports.rest.gui(value.type, function(itemGui){
                       gui.connectivity.transports.rest.item(value.id, function(item) {
                           var tabs = { 
                                   tabs: [
                                      {
                                       title: 'General',
                                       fields: itemGui,
                                      },
                                      {
                                       title: 'Networks',
                                       fields: [],
                                      },
                                   ]
                               };
                           gui.forms.launchModal(gettext('Edit transport')+' '+value.name, tabs, item, function(form_selector, closeFnc) {
                               var fields = gui.forms.read(form_selector);
                               fields.data_type = value.type;
                               fields.nets_positive = false;
                               gui.connectivity.transports.rest.save(fields, function(data) { // Success on put
                                   closeFnc();
                                   refreshFnc();
                               }, gui.failRequestModalFnc(gettext('Error creating transport')) // Fail on put, show modal message
                               );
                               return false;
                           });
                       });
                   });
            },
            onNew: function(type, table, refreshFnc) {
                gui.connectivity.transports.rest.gui(type, function(itemGui) {
                    var tabs = { 
                        tabs: [
                           {
                            title: 'General',
                            fields: itemGui,
                           },
                           {
                            title: 'Networks',
                            fields: [
                                gui.forms.guiField('networks', 'multichoice', gettext('Available for networks'), 
                                        gettext('Select networks that will see this transport'), [], []),
                                gui.forms.guiField('nets_positive', 'checkbox', gettext('Transport active for selected networks'),
                                        gettext('If active, transport will only be available on selected networks. If inactive, transport will be available form any net EXCEPT selected networks'),
                                        true) 
                            ],
                           },
                        ]
                    };
                    gui.forms.launchModal(gettext('New transport'), tabs, undefined, function(form_selector, closeFnc) {
                        var fields = gui.form.read(form_selector);
                        // Append "own" fields, in this case data_type
                        fields.data_type = type;
                        fields.nets_positive = false;
                        gui.connectivity.transports.rest.create(fields, function(data) { // Success on put
                            closeFnc();
                            refreshFnc();
                        }, gui.failRequestModalFnc(gettext('Error creating transport')) // Fail on put, show modal message
                        );
                    });
                });
            },
            onDelete: function(value, event, table, refreshFncs) {
                // TODO: Add confirmation to deletion
                gui.connectivity.transports.rest.del(value.id, function(){
                    refreshFnc();
                }, gui.failRequestModalFnc(gettext('Error removing transport')) );
            },
        });
        gui.connectivity.networks.table({
            rowSelect : 'multi',
            container : 'networks-placeholder',
            buttons : [ 'new', 'edit', 'delete', 'xls' ],
        });
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