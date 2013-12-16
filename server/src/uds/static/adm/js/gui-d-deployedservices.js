/* jshint strict: true */
gui.deployedservices = new GuiElement(api.deployedservices, 'deployedservices');
 

gui.deployedservices.link = function(event) {
    "use strict";
    gui.clearWorkspace();
    
    // Clears the details
    // Memory saver :-)
    var prevTables = [];
    var clearDetails = function() {
        $.each(prevTables, function(undefined, tbl){
            var $tbl = $(tbl).dataTable();
            $tbl.fnClearTable();
            $tbl.fnDestroy();
        });
        
        $('#assigned-services-placeholder').empty();
        $('#cache-placeholder').empty();
        $('#transports-placeholder').empty();
        $('#groups-placeholder').empty();
        $('#logs-placeholder').empty();
        
        $('#detail-placeholder').addClass('hidden');
        
        prevTables = [];
    };
    
    // Fills up the list of available services
    api.providers.allServices(function(services){
        var availableServices = {};
        
        $.each(services, function(undefined, service){
            availableServices[service.id] = service;    
        });

        gui.doLog('Available services', availableServices);
        api.templates.get('deployedservices', function(tmpl) {
            gui.appendToWorkspace(api.templates.evaluate(tmpl, {
                deployed_services : 'deployed-services-placeholder',
                assigned_services : 'assigned-services-placeholder',
                cache : 'cache-placeholder',
                groups : 'groups-placeholder',
                transports : 'transports-placeholde',
                logs : 'logs-placeholder',
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
                onRowDeselect: function() {
                    clearDetails();
                },
                onRowSelect : function(selected) {
                    var dps = selected[0];
                    gui.doLog('Selected services pool', dps);
                    
                    clearDetails();
                    $('#detail-placeholder').removeClass('hidden');
                    // If service does not supports cache, do not show it
                    try {
                        var service = availableServices[dps.service_id];
                    } catch (e) {
                        gui.doLog('Exception on rowSelect', e);
                        gui.notify(gettext('Error processing deployed service'), 'danger');
                        return;
                    }
                    
                    var cachedItems = null;
                    // Shows/hides cache
                    if( service.info.uses_cache || service.info.uses_cache_l2 ) {
                        $('#cache-placeholder_tab').removeClass('hidden');
                        cachedItems = api.deployedservices.detail(dps.id, 'cache');
                    } else {
                        $('#cache-placeholder_tab').addClass('hidden');
                    }
                    var groups = null;
                    // Shows/hides groups
                    if( service.info.must_assign_manually ) {
                        $('#groups-placeholder_tab').removeClass('hidden');
                        
                    } else {
                        $('#groups-placeholder_tab').addClass('hidden');
                    }
                    
                    var assignedServices =  new GuiElement(api.deployedservices.detail(dps.id, 'services'), 'services');
                    var assignedServicesTable = assignedServices.table({
                        container: 'assigned-services-placeholder',
                        rowSelect: 'single',
                    });
                    
                    prevTables.push(assignedServicesTable);
                },
                // Preprocess data received to add "icon" to deployed service
                onData: function(data) {
                    gui.doLog('onData', data);
                    $.each(data, function(index, value){
                        try {
                            var service = availableServices[value.service_id];
                            var style = 'display:inline-block; background: url(data:image/png;base64,' +
                                service.info.icon + '); ' + 'width: 16px; height: 16px; vertical-align: middle;';
                            
                            value.name = '<span style="' + style + '"></span> ' +  value.name;
                            
                            value.parent = service.name;
                        } catch (e) {
                            value.name = '<span class="fa fa-asterisk text-alert"></span> ' + value.name; 
                            value.parent = gettext('unknown (needs reload)');
                        }
                    });
                }
            });
        });
    });
      
};
