(function(gui, $, undefined) {
	 
	// "public" methods
	gui.doLog = function(data) {
		if( gui.debug  ) {
			try {
				console.log(data);
			} catch (e) {
				// nothing can be logged
			}
			
		}
	}
	
	gui.table = function(table_id) {
		return '<div class="well"><table class="display" id="' + table_id + '"></table></div>'		
	}
	
	gui.clearWorkspace = function() {
		$('#content').empty();
	};
	
	gui.appendToWorkspace = function(data) {
		$(data).appendTo('#content');
	};
	
	gui.dashboard = function() {
		gui.clearWorkspace();
	};
	
	gui.providers = function() {
		gui.clearWorkspace();
		
    	api.providers.list(function(data){
        	gui.appendToWorkspace( gui.table('providers_table') );
        	var arr = [];
        	$.each(data, function(index, value){
        		arr.push([value.name, value.type_name, value.services_count]);
        	});
            $('#providers_table').dataTable( {
                "aaData": arr,
                "aoColumns": [
                    { "sTitle": gettext("Name") },
                    { "sTitle": gettext("Type") },
                    { "sTitle": gettext("Number of Services") },
                ],
	            "oLanguage": {
	                "sLengthMenu": gettext("Display _MENU_ records per page"),
	                "sZeroRecords": gettext("Nothing found - sorry"),
	                "sInfo": gettext("Showing _START_ to _END_ of _TOTAL_ records"),
	                "sInfoEmpty": gettext("Showing 0 to 0 of 0 records"),
	                "sInfoFiltered": gettext("(filtered from _MAX_ total records)"),
	                "sProcessing": gettext("Please wait, processing"),
	                "sSearch": gettext("Search"),
	                "sInfoThousands": django.formats.THOUSAND_SEPARATOR,
	                "oPaginate": {
		                "sFirst": gettext("First"),
		                "sLast": gettext("Last"),
		                "sNext": gettext("Next"),
		                "sPrevious": gettext("Previous"),
	                }
	                
	            },           
            } );            	
    	});
		
		return false;
	}
	
	var sidebarLinks = [
	     { id: 'dashboard', exec: gui.dashboard },
	     { id: 'service_providers', exec: gui.providers },
	     { id: 'authenticators', exec: gui.dashboard },
	     { id: 'osmanagers', exec: gui.dashboard },
	     { id: 'connectivity', exec: gui.dashboard },
	     { id: 'deployed_services', exec: gui.dashboard },
	];
	
	gui.init = function() {
		$.each(sidebarLinks, function(index, value){
			gui.doLog('Adding ' + value.id)
			$('#'+value.id).click(value.exec);
		});
	};
	
	// Public attributes 
	gui.debug = true;
}(window.gui = window.gui || {}, jQuery));
