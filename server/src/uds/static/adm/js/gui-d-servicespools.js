/* jshint strict: true */
gui.servicesPools = new GuiElement(api.servicesPools, 'servicespools');
 

gui.servicesPools.link = function(event) {
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
        
        $('#assigned-services-placeholder_tbl').empty();
        $('#assigned-services-placeholder_log').empty();
        $('#cache-placeholder_tbl').empty();
        $('#cache-placeholder_log').empty();
        $('#transports-placeholder').empty();
        $('#groups-placeholder').empty();
        $('#logs-placeholder').empty();
        
        $('#detail-placeholder').addClass('hidden');
        
        prevTables = [];
    };
    
    // On change base service
    var preFnc = function(formId) {
        var $fld = $(formId + ' [name="service_id"]');
        var $osmFld = $(formId + ' [name="osmanager_id"]');
        var selectors = [];
        $.each(['initial_srvs', 'cache_l1_srvs', 'cache_l2_srvs', 'max_srvs'], function(index, value){
            selectors.push(formId + ' [name="' + value + '"]');
        });
        var $cacheFlds = $(selectors.join(','));
        var $cacheL2Fld = $(formId + ' [name="cache_l2_srvs"]');
        var $publishOnSaveFld = $(formId + ' [name="publish_on_save"]');
        $fld.on('change', function(event){
            if($fld.val() != -1 ) {
                api.providers.service($fld.val(), function(data){
                    gui.doLog('Onchange', data);
                    if( data.info.needs_manager === false ) {
                        $osmFld.prop('disabled', 'disabled');
                    } else {
                        $osmFld.prop('disabled', false);
                    }
                    
                    if( data.info.uses_cache === false ) {
                        $cacheFlds.prop('disabled', 'disabled');
                    } else {
                        $cacheFlds.prop('disabled', false);
                        if( data.info.uses_cache_l2 === false ) {
                            $cacheL2Fld.prop('disabled', 'disabled');
                        } else {
                            $cacheL2Fld.prop('disabled', false);
                        }
                    }
                    
                    if( data.info.needs_publication === false ) {
                        $publishOnSaveFld.bootstrapSwitch('setDisabled', true);
                    } else {
                        $publishOnSaveFld.bootstrapSwitch('setDisabled', false);
                    } 
                    
                    if($osmFld.hasClass('selectpicker'))
                        $osmFld.selectpicker('refresh');
                    
                    
                });
            }
        });
    };
    
    // Fills up the list of available services
    api.providers.allServices(function(services){
        var availableServices = {};
        
        $.each(services, function(undefined, service){
            availableServices[service.id] = service;    
        });

        gui.doLog('Available services', availableServices);
        api.templates.get('services_pool', function(tmpl) {
            gui.appendToWorkspace(api.templates.evaluate(tmpl, {
                deployed_services : 'deployed-services-placeholder',
                assigned_services : 'assigned-services-placeholder',
                cache : 'cache-placeholder',
                groups : 'groups-placeholder',
                transports : 'transports-placeholder',
                publications: 'publications-placeholder',
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
            
            /*
             * Services pools part
             */
            var tableId = gui.servicesPools.table({
                container : 'deployed-services-placeholder',
                rowSelect : 'single',
                buttons : [ 'new', 'edit', 'delete', { text: gettext('Test'), css: 'disabled', click: testClick, select: testSelect }, 'xls' ],
                onRowDeselect: function() {
                    clearDetails();
                },
                onRowSelect : function(selected) {
                    var servPool = selected[0];
                    gui.doLog('Selected services pool', servPool);
                    
                    clearDetails();
                    $('#detail-placeholder').removeClass('hidden');
                    
                    var service = null;
                    try {
                        service = availableServices[servPool.service_id];
                    } catch (e) {
                        gui.doLog('Exception on rowSelect', e);
                        gui.notify(gettext('Error processing deployed service'), 'danger');
                        return;
                    }
                    
                    /* 
                     * Cache Part
                     */
                    
                    var cachedItems = null;
                    // If service does not supports cache, do not show it
                    // Shows/hides cache
                    if( service.info.uses_cache || service.info.uses_cache_l2 ) {
                        $('#cache-placeholder_tab').removeClass('hidden');
                        cachedItems = new GuiElement(api.servicesPools.detail(servPool.id, 'cache'), 'cache');
                        // Cached items table
                        var prevCacheLogTbl = null;
                        var cachedItemsTable = cachedItems.table({
                            container : 'cache-placeholder_tbl',
                            buttons : [ 'delete', 'xls' ],
                            rowSelect : 'single',
                            onRowSelect : function(selected) {
                                var cached = selected[0];
                                if( prevAssignedLogTbl ) {
                                    var $tbl = $(prevCacheLogTbl).dataTable();
                                    $tbl.fnClearTable();
                                    $tbl.fnDestroy();
                                }
                                prevCacheLogTbl = cachedItems.logTable(cached.id, {
                                    container : 'cache-placeholder_log',
                                });
                            } 
                        });
                        prevTables.push(cachedItemsTable);
                    } else {
                        $('#cache-placeholder_tab').addClass('hidden');
                    }
                    
                    /*
                     * Groups part
                     */
                    
                    var groups = null;
                    // Shows/hides groups
                    if( service.info.must_assign_manually === false ) {
                        $('#groups-placeholder_tab').removeClass('hidden');
                        groups = new GuiElement(api.servicesPools.detail(servPool.id, 'groups'), 'groups');
                        // Groups items table
                        var groupsTable = groups.table({
                            container : 'groups-placeholder',
                            rowSelect : 'single',
                            buttons : [ 'new', 'delete', 'xls' ],
                            onData : function(data) {
                                $.each(data, function(undefined, value){
                                    value.group_name = '<b>' + value.auth_name + '</b>\\' + value.name;
                                });
                            },
                        });
                        prevTables.push(groupsTable);
                    } else {
                        $('#groups-placeholder_tab').addClass('hidden');
                    }
                    
                    /*
                     * Assigned services part
                     */
                    var prevAssignedLogTbl = null;
                    var assignedServices =  new GuiElement(api.servicesPools.detail(servPool.id, 'services'), 'services');
                    var assignedServicesTable = assignedServices.table({
                            container: 'assigned-services-placeholder_tbl',
                            rowSelect: 'single',
                            buttons: service.info.must_assign_manually ? ['new', 'delete', 'xls'] : ['delete', 'xls'],
                            onRowSelect: function(selected) {
                                var service = selected[0];
                                if( prevAssignedLogTbl ) {
                                    var $tbl = $(prevAssignedLogTbl).dataTable();
                                    $tbl.fnClearTable();
                                    $tbl.fnDestroy();
                                }
                                prevAssignedLogTbl = assignedServices.logTable(service.id, {
                                    container : 'assigned-services-placeholder_log',
                                });
                            }
                    });
                    // Log of assigned services (right under assigned services)
                    
                    prevTables.push(assignedServicesTable);
                    
                    /*
                     * Transports part
                     */
                    
                    var transports =  new GuiElement(api.servicesPools.detail(servPool.id, 'transports'), 'transports');
                    // Transports items table
                    var transportsTable = transports.table({
                        container: 'transports-placeholder',
                        rowSelect: 'single',
                        buttons : [ 'new', 'delete', 'xls' ],
                        onData: function(data) {
                            $.each(data, function(undefined, value){
                                var style = 'display:inline-block; background: url(data:image/png;base64,' +
                                            value.type.icon + '); ' + 'width: 16px; height: 16px; vertical-align: middle;';
                                value.trans_type = value.type.name;
                                value.name = '<span style="' + style + '"></span> ' + value.name;
                            });
                        }
                    });
                    prevTables.push(transportsTable);
                    
                    /*
                     * Publications part
                     */
                    var publications = null;
                    if( service.info.needs_publication ) {
                        $('#publications-placeholder_tab').removeClass('hidden');
                        var pubApi = api.servicesPools.detail(servPool.id, 'publications');
                        publications = new GuiElement(pubApi, 'publications');
                        // Publications table
                        var publicationsTable = publications.table({
                            container : 'publications-placeholder',
                            rowSelect : 'single',
                            buttons : [ 'new', { 
                                                    text: gettext('Cancel'), 
                                                    css: 'disabled', 
                                                    click: function(val, value, btn, tbl, refreshFnc) {
                                                        gui.doLog(val);
                                                    }, 
                                                    select: function(val, value, btn, tbl, refreshFnc) {
                                                        if( !val ) {
                                                            $(btn).removeClass('btn3d-info').addClass('disabled');
                                                            return;
                                                        }
                                                        if( ['P','W','L'].indexOf(val.state) > 0 ) { // Waiting for publication, Preparing or running
                                                            $(btn).removeClass('disabled').addClass('btn3d-info');
                                                        }
                                                    },
                                                }, 
                                        'xls' ],
                            onNew: function(action, tbl, refreshFnc) {
                                gui.doLog('New publication');
                                pubApi.invoke('publish', function(){
                                    gui.doLog('Success');
                                }, gui.failRequestModalFnc(gettext('Publication failed')) );
                            },
                        });
                        prevTables.push(publicationsTable);
                        
                    } else {
                        $('#publications-placeholder_tab').addClass('hidden');
                    }
                    
                    /*
                     * Log table
                     */
                    
                    var logTable = gui.servicesPools.logTable(servPool.id, {
                        container : 'logs-placeholder',
                    });
                    
                    prevTables.push(logTable);
                },
                // Pre-process data received to add "icon" to deployed service
                onData: function(data) {
                    gui.doLog('onData', data);
                    $.each(data, function(index, value){
                        try {
                            var service = availableServices[value.service_id];
                            var style = 'display:inline-block; background: url(data:image/png;base64,' +
                                service.info.icon + '); ' + 'width: 16px; height: 16px; vertical-align: middle;';

                            if( value.restrained ) {
                                value.name = '<span class="fa fa-exclamation text-danger"></span> ' + value.name;
                                value.state = gettext('Restrained');
                            }
                            
                            value.name = '<span style="' + style + '"></span> ' + value.name;
                            
                            value.parent = service.name;
                        } catch (e) {
                            value.name = '<span class="fa fa-asterisk text-alert"></span> ' + value.name; 
                            value.parent = gettext('unknown (needs reload)');
                        }
                    });
                },
                onNew: gui.methods.typedNew(gui.servicesPools, gettext('New service pool'), gettext('Error creating service pool'), {
                    guiProcessor: function(guiDef) { // Create has "save on publish" field
                        gui.doLog(guiDef);
                        var newDef = [].concat(guiDef).concat([{
                                'name': 'publish_on_save',
                                'value': true,
                                'gui': {
                                    'label': gettext('Publish on creation'),
                                    'tooltip': gettext('If selected, will initiate the publication on service inmediatly pool after creation'),
                                    'type': 'checkbox',
                                    'order': 150,
                                    'defvalue': true,
                                },
                            }]);
                        gui.doLog(newDef);
                        return newDef;
                    },
                    preprocessor: preFnc,
                    }),
                onEdit: gui.methods.typedEdit(gui.servicesPools, gettext('Edit service pool'), gettext('Error saving service pool')),
                onDelete: gui.methods.del(gui.servicesPools, gettext('Delete service pool'), gettext('Error deleting service pool')),
            });
        });
    });
      
};
