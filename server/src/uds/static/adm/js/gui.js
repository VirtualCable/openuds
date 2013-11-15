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
                "sLengthMenu": gettext("_MENU_ records per page"),
                "sZeroRecords": gettext("Empty"),
                "sInfo": gettext("Records _START_ to _END_ of _TOTAL_"),
                "sInfoEmpty": gettext("No records"),
                "sInfoFiltered": gettext("(filtered from _MAX_ total records)"),
                "sProcessing": gettext("Please wait, processing"),
                "sSearch": gettext("Filter"),
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
		
		return '<div class="panel panel-primary"><div class="panel-heading">'+
				'<h3 class="panel-title"><span class="fa fa-'+ options.icon + '"></span> ' + title + '</h3></div>'+
		        '<div class="panel-body"><table class="table table-striped table-bordered table-hover" id="' + table_id + '" border="0" cellpadding="0" cellspacing="0" width="100%"></table></div></div>';		
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
	
	gui.deployed_services = function() {
		gui.clearWorkspace();
		gui.appendToWorkspace(gui.breadcrumbs(gettext('Deployed services')));
	}
	
	gui.setLinksEvents = function() {
		var sidebarLinks = [
			           	     { id: 'lnk-dashboard', exec: gui.dashboard },
			           	     { id: 'lnk-service_providers', exec: gui.providers.link },
			           	     { id: 'lnk-authenticators', exec: gui.authenticators.link },
			           	     { id: 'lnk-osmanagers', exec: gui.osmanagers.link },
			           	     { id: 'lnk-connectivity', exec: gui.connectivity.link },
			           	     { id: 'lnk-deployed_services', exec: gui.deployed_services },
			           	];
		$.each(sidebarLinks, function(index, value){
			gui.doLog('Adding ' + value.id)
			$('.'+value.id).unbind('click').click(function(event) {
                if($('.navbar-toggle').css('display') !='none') {
                    $(".navbar-toggle").trigger( "click" );
                }
                $('html, body').scrollTop(0);
                value.exec(event);
			});
		});
	}
	
	
	gui.init = function() {
		gui.setLinksEvents();
	};
	
	// Public attributes 
	gui.debug = true;
}(window.gui = window.gui || {}, jQuery));

function GuiElement(restItem, name) {
	this.rest = restItem;
	this.name = name;
	this.types = {}
	this.init();
}

// all gui elements has, at least, name && type
// Types must include, at least: type, icon
GuiElement.prototype = {
		init: function() {
			gui.doLog('Initializing ' + this.name);
			var $this = this;
        	this.rest.types(function(data){
        		var styles = '';
        		$.each(data, function(index, value){
        			var className = $this.name + '-' + value.type;
        			$this.types[value.type] = { css: className, name: value.name || '', description: value.description || '' };
        			gui.doLog('Creating style for ' + className )
        			var style = '.' + className  + 
        				' { display:inline-block; background: url(data:image/png;base64,' + value.icon + '); ' +
        				'width: 16px; height: 16px; vertical-align: middle; } ';
        			styles += style;
        		});
        		if(styles != '') {
        			styles = '<style media="screen">' + styles + '</style>'
        			$(styles).appendTo('head');
        		}
        	});
		},
		table: function(options) {
			// Options (all are optionals)
			// rowSelect: 'single' or 'multi'
			// container: ID of the element that will hold this table (will be emptied)
			// rowSelectFnc: function to invoke on row selection. receives 1  array - node : TR elements that were selected
			// rowDeselectFnc: function to invoke on row deselection. receives 1  array - node : TR elements that were selected
			gui.doLog('Composing table for ' + this.name);
			var tableId = this.name + '-table';
			var $this = this;
			this.rest.tableInfo(function(data){
				var title = data.title;
				var columns = [];
				$.each(data.fields,function(index, value) {
					for( var v in value ){
						var options = value[v];
						var column = { mData: v };
						column.sTitle = options.title;
						if( options.type )
							column.sType = options.type;
						if( options.width )
							column.sWidth = options.width;
						if( options.visible != undefined )
							column.bVisible = options.visible;
						if( options.sortable != undefined )
							column.bSortable = options.sortable;
						if( options.searchable != undefined )
							column.bSearchable = options.searchable;

						// Fix name columm so we can add a class icon
						if( v == 'name' ) {
							column.sType ='html'
						}
						
	                    columns.push(column);
					}
				});
				gui.doLog(columns);
				
				var processResponse = function(data) {
					// If it has a "type" column
					try {
						if( data[0].type != undefined ) {
							$.each(data, function(index, value){
								var type = $this.types[value.type];
								data[index].name = '<span class="' + type.css + '"> </span> ' + value.name
							});
						}
					} catch (e) {
						return;
					}
				};
				
				$this.rest.get({
					success: function(data) {
						processResponse(data);
			        	var table = gui.table(title, tableId);
			        	if( options.container == undefined ) {
			        		gui.appendToWorkspace('<div class="row"><div class="col-lg-12">' + table + '</div></div>');
			        	} else {
			        		$('#'+options.container).empty();
			        		$('#'+options.container).append(table);
			        	}
			        	
			        	var btns = [
			        	];
			        	
			        	if( options.buttons ) {
			        		
			        		// methods for buttons click
			        		var editFnc = function() {
			        			gui.doLog('Edit');
			        			gui.doLog(this);
			        		};
			        		var deleteFnc = function() {
			        			gui.doLog('Delete');
			        			gui.doLog(this);
			        		};
			        		var refreshFnc = function(btn) {
			        			// Refreshes table content
			        			gui.doLog('Refresh');
			        			gui.doLog(this);
			        			gui.doLog(btn);
			        			var tbl = $('#' + tableId).dataTable();
			        			var width = $(btn).width();
			        			var saved = $(btn).html();
			        			$(btn).addClass('disabled').html('<span class="fa fa-spinner fa-spin"></span>').width(width);
			        			$this.rest.get({
			    					success: function(data) {
			    						processResponse(data);
			    						tbl.fnClearTable();
			    						tbl.fnAddData(data);
					        			$(btn).removeClass('disabled').html(saved);
			    					}
			        			});
			        		}
			        		
			        		// methods for buttons on row select
			        		var editSelected = function(btn, obj, node) {
			        			var sel = this.fnGetSelectedData();
			        			if( sel.length == 1) {
			        				$(btn).removeClass('disabled').addClass('btn-info');
			        			} else {
			        				$(btn).removeClass('btn-info').addClass('disabled');
			        			}
			        		};
			        		var deleteSelected = function(btn, obj, node) {
			        			var sel = this.fnGetSelectedData();
			        			if( sel.length > 0) {
			        				$(btn).removeClass('disabled').addClass('btn-warning');
			        			} else {
			        				$(btn).removeClass('btn-warning').addClass('disabled');
			        			}
			        		};
			        		
			        		$.each(options.buttons, function(index, value){
			        			var btn = undefined;
			        			switch(value) {
			        				case 'edit':
				        				btn = {
				        					"sExtends": "text",
				        					"sButtonText": gettext('Edit'),
				        					"fnSelect": editSelected,
				        					"fnClick": editFnc,
				        					"sButtonClass": "disabled"
				        				};
				        				break;
			        				case 'delete':
				        				btn = {
				        					"sExtends": "text",
				        					"sButtonText": gettext('Delete'),
				        					"fnSelect": deleteSelected,
				        					"fnClick": deleteFnc,
				        					"sButtonClass": "disabled"
				        				};
				        				break;
			        				case 'refresh':
				        				btn = {
				        					"sExtends": "text",
				        					"sButtonText": gettext('Refresh'),
				        					"fnClick": refreshFnc,
				        					"sButtonClass": "btn-info"
				        				};
				        				break;
			        				case 'csb':
										btn = {
			        						"sExtends": "csv",
			        						"sTitle": title,
			        						"sFileName": title + '.csv',
										};
										break;
			        				case 'pdf':
			        					btn = {
										    "sExtends": "pdf",
										    "sTitle": title,
										    "sPdfMessage": "Summary Info",
										    "sFileName": title + '.pdf',
										    "sPdfOrientation": "portrait"
			        					};
			        					break;
			        			}
			        			
			        			if( btn != undefined )		
			        				btns.push(btn);
			        		});
			        	}
			        	
			        	// Initializes oTableTools
			        	oTableTools = {
							"aButtons": btns 
			        	};
			        	if( options.rowSelect ) {
		            		oTableTools.sRowSelect = options.rowSelect
			        	}
			        	if( options.rowSelectFnc ) {
			        		oTableTools.fnRowSelected = options.rowSelectFnc
			        	}
			        	if( options.rowDeselectFnc ) {
			        		oTableTools.fnRowDeselected  = options.rowDeselectFnc
			        	}
			        	
			        	
			            $('#' + tableId).dataTable({
			                "aaData": data,
			                "aoColumns": columns,
				            "oLanguage": gui.dataTablesLanguage,
				            "oTableTools": oTableTools,
							// First is upper row, second row is lower (pagination) row
							"sDom": "<'row'<'col-xs-6'T><'col-xs-6'f>r>t<'row'<'col-xs-5'i><'col-xs-7'p>>",
							
			            });
			            $('#' + tableId + '_filter input').addClass('form-control');
						var tableTop = $('#'+tableId).offset().top;
						gui.doLog(tableTop);
						//$('html, body').animate({ scrollTop: tableTop });
						if( options.scroll ) 
							$('html, body').scrollTop(tableTop);
					}
				});
			});
			return '#' + tableId;
		}
		
};
