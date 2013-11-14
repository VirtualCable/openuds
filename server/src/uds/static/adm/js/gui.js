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
	
	// Several convenience "constants"
	gui.dataTablesLanguage = {
                "sLengthMenu": gettext("Display _MENU_ records per page"),
                "sZeroRecords": gettext("Nothing found - sorry"),
                "sInfo": gettext("Showing record _START_ to _END_ of _TOTAL_"),
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
	};

	gui.table = function(title, table_id, options) {
		if( options == undefined )
			options = { 'size': 12, 'icon': 'table'};
		if( options.size == undefined )
			options.size = 12;
		if( options.icon == undefined )
			options.icon = 'table';
		
		return '<div class="col-lg-' + options.size + '"><div class="panel panel-primary"><div class="panel-heading">'+
				'<h3 class="panel-title"><span class="fa fa-'+ options.icon + '"></span> ' + title + '</h3></div>'+
		        '<div class="panel-body"><table class="display" id="' + table_id + '"></table></div></div></div>';		
	}
	
	gui.breadcrumbs = function(path) {
		var items = path.split('/');
		var active = items.pop();
		var list = '';
		$.each(items, function(index, value){
			list += '<li><a href="#">' + value + '</a></li>';
		});
		list += '<li class="active">' + active + '</li>';
		
		return '<div class="row"><div class="col-lg-12"><ol class="breadcrumb">'+ list + "</ol></div></div>";
		
	}
	
	gui.clearWorkspace = function() {
		$('#page-wrapper').empty();
	};

	gui.appendToWorkspace = function(data) {
		$(data).appendTo('#page-wrapper');
	};

	
	// Links methods
	gui.dashboard = function() {
		gui.clearWorkspace();
		gui.appendToWorkspace(gui.breadcrumbs('Dasboard'));
		gui.doLog(this);
	};
	
	gui.osmanagers = function() {
		gui.clearWorkspace();
		gui.appendToWorkspace(gui.breadcrumbs('OS Managers'));
		
	}

	gui.connectivity = function() {
		gui.clearWorkspace();
		gui.appendToWorkspace(gui.breadcrumbs(gettext('Connectivity')));
	}
	
	gui.deployed_services = function() {
		gui.clearWorkspace();
		gui.appendToWorkspace(gui.breadcrumbs(gettext('Deployed services')));
	}
	
	gui.setLinksEvents = function() {
		var sidebarLinks = [
			           	     { id: 'lnk-dashboard', exec: gui.dashboard },
			           	     { id: 'lnk-service_providers', exec: gui.providers.link },
			           	     { id: 'lnk-authenticators', exec: gui.authenticators.link },
			           	     { id: 'lnk-osmanagers', exec: gui.osmanagers },
			           	     { id: 'lnk-connectivity', exec: gui.connectivity },
			           	     { id: 'lnk-deployed_services', exec: gui.deployed_services },
			           	];
		$.each(sidebarLinks, function(index, value){
			gui.doLog('Adding ' + value.id)
			$('.'+value.id).unbind('click').click(value.exec);
		});
	}
	
	
	gui.init = function() {
		gui.setLinksEvents();
	};
	
	// Public attributes 
	gui.debug = true;
}(window.gui = window.gui || {}, jQuery));

function GuiElement(restItem) {
	this.rest = restItem;
	this.init();
}

GuiElement.prototype = {
		init: function() {
			gui.doLog('Initializing ' + this.rest.path);
			var $this = this;
        	this.rest.types(function(data){
        		var styles = '<style media="screen">';
        		$.each(data, function(index, value){
        			var className = $this.rest.path + '-' + value.type;
        			gui.doLog('Creating style for ' + className )
        			var style = '.' + className  + 
        				' { display:inline-block; background: url(data:image/png;base64,' + value.icon + '); ' +
        				'width: 16px; height: 16px; vertical-align: middle; } ';
        			styles += style;
        		});
        		styles += '</style>'
        		$(styles).appendTo('head');
        	});
		},
		table: function(options) {
			// Empty container_id first
			gui.doLog('Composing table for ' + this.rest.path);
			var tableId = this.rest.path + '-table';
			var $this = this;
			this.rest.tableInfo(function(data){
				var title = data.title;
				var columns = [];
				$.each(data.fields,function(index, value) { 
					for( var v in value ){
						var options = value[v];
						gui.doLog(options);
						var column = { mData: v };
						column.sTitle = options.title;
						if( options.type )
							column.sType = options.type;
						if( options.width )
							column.sWidth = options.width;
						if( options.visible != undefined )
							column.bVisible = options.visible;
	                    columns.push(column);
					}
				});
				gui.doLog(columns);
				$this.rest.get({
					success: function(data) {
			        	var table = gui.table(title, tableId, options);
			        	gui.appendToWorkspace('<div class="row">' + table + '</div>');
			            $('#' + tableId).dataTable( {
			                "aaData": data,
			                "aoColumns": columns,
				            "oLanguage": gui.dataTablesLanguage,           
			            } )
					}
				});
			});
			return '#' + tableId;
		}
		
};

// Compose gui API

// Service providers
gui.providers = new GuiElement(api.providers);
gui.providers.link = function(event) {
	gui.clearWorkspace();
	gui.appendToWorkspace(gui.breadcrumbs(gettext('Service Providers')));
	
	var tableId = gui.providers.table();
	
	return false;
};

gui.authenticators = new GuiElement(api.authenticators);
gui.authenticators.link = function(event) {
	gui.clearWorkspace();
	gui.appendToWorkspace(gui.breadcrumbs(gettext('Authenticators')));
	
	gui.authenticators.table();
	
	return false;
};