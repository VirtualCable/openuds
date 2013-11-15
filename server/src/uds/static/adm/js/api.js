(function(api, $, undefined) {
	 
	// "public" methods
	api.doLog = function(data) {
		if( api.debug  ) {
			try {
				console.log(data);
			} catch (e) {
				// nothing can be logged
			}
			
		}
	}
	
	api.getJson = function (path, success_fnc) {
		url = api.url_for(path)
		api.doLog('Ajax GET Json for "' + url + '"');
		$.ajax({
			url: url,
			type: "GET",
			dataType: "json",
			success: function(data) {
				api.doLog('Success on "' + url + '".');
				api.doLog('Received ' + JSON.stringify(data));
				if( success_fnc != undefined ){
					api.doLog('Executing success method')
					success_fnc(data);
				}
			},
			beforeSend: function (request) {
	            request.setRequestHeader(api.auth_header, api.token);
	        },
		});
	};
	
	// Public attributes 
	api.debug = false;
}(window.api = window.api || {}, jQuery));


// Great part of UDS REST api provides same methods.
// We will take advantage of this and save a lot of nonsense, prone to failure code :-)

function BasicModelRest(path) {
	this.path = path || "";
	this.cached_types = undefined;
	this.cached_tableInfo = undefined;
}

BasicModelRest.prototype = {
		get: function(options, alternate_url) {
			if( options == undefined ){
				options = {};
			}
			var path = alternate_url || this.path;
			if( options.id != undefined )
				path += '/' + options.id;
			api.getJson(path, options.success);
		},
		types: function(success_fnc, alternate_url) {
			// Cache types locally, will not change unless new broker version
			if( this.cached_types ) {
				if( success_fnc ) {
					success_fnc(this.cached_types);
				}
			}
			else {
				var $this = this;
				var path = this.path + '/types';
				if( alternate_url != undefined ) 
					path = alternate_url;
				api.getJson( path, function(data) {
					$this.cached_types = data;
					if( success_fnc ) {
						success_fnc($this.cached_types);
					}
				});
			}
		},
		
		tableInfo: function(success_fnc, alternate_url) {
			// Cache types locally, will not change unless new broker version
			if( this.cached_tableInfo ) {
				if( success_fnc ) {
					success_fnc(this.cached_tableInfo);
				}
				return;
			}
			var $this = this;
			var path = this.path + '/tableinfo';
			if( alternate_url != undefined )
				path = alternate_url;
			
			api.getJson( path, function(data) {
				$this.cached_tableInfo = data;
				if( success_fnc ) {
					success_fnc($this.cached_tableInfo);
				}
			});
			
		},

};

// For REST of type /auth/[id]/users, /services/[id]/users, ...
function DetailModelRestApi(parentApi, path) {
	this.parentPath = parentApi.path;
	this.path = path;
}

DetailModelRestApi.prototype = {
		// Generates a basic model with fixed methods for "detail" models
		detail: function(parentId) {
			var $this = this;
			var rest = new BasicModelRest(this.parentPath + '/' + parentId + '/' + this.path);
			
			// Overwrite types, detail do not have types
			rest.types = function() {
				return []; // No types at all
			}
			
			// And overwrite tableInfo
			var parentTableInfo = rest.tableInfo;
			rest.tableInfo = function(success_fnc, alternate_url) {
				if( alternate_url == undefined ) 
					alternate_url = $this.parentPath + '/tableinfo/' + parentId + '/' + $this.path; 
				parentTableInfo( success_fnc, alternate_url )
			}
			return rest;
		}
};


// Populate api

api.providers = new BasicModelRest('providers');
//api.services = new BasicModelRest('services');
api.authenticators = new BasicModelRest('authenticators');
api.authenticators.users = new DetailModelRestApi(api.authenticators, 'users');

api.osmanagers = new BasicModelRest('osmanagers');
api.transports = new BasicModelRest('transports');
api.networks = new BasicModelRest('networks');


// -------------------------------
// Templates related
// This is not part of REST api provided by UDS, but it's part of the api needed for the admin app
// -------------------------------
(function(templates, $){
	templates.cache = {}; // Will cache templates locally. If name contains '?', data will not be cached and always re-requested
	templates.get = function(name, success_fnc) {
		if( !name.contains('?') ) {
			if( templates.cache[name] != undefined ) {
				if( success_fnc != undefined ) {
					success_fnc(templates.cache[name]);
				}
				return;
			}
		}
		$.ajax({
			url: '/adm/tmpl/' + name,
			type: "GET",
			dataType: "text",
			success: function(data) {
				templates.cache[name] = data;
				api.doLog('Success getting template "' + name + '".');
				api.doLog('Received: ' + data);
				if( success_fnc != undefined ){
					api.doLog('Executing success method')
					success_fnc(data);
				}
			},
		});
	};
	
	// Simple JavaScript Templating
	// Based on John Resig - http://ejohn.org/ - MIT Licensed
	templates.eval = function tmpl(str, data){
		    // Figure out if we're getting a template, or if we need to
		    // load the template - and be sure to cache the result.
		    var fn = 		     
		      // Generate a reusable function that will serve as a template
		      // generator (and which will be cached).
		      new Function("obj",
		        "var p=[],print=function(){p.push.apply(p,arguments);};" +
		       
		        // Introduce the data as local variables using with(){}
		        "with(obj){p.push('" +
		       
		        // Convert the template into pure JavaScript
		        str
		          .replace(/[\r\t\n]/g, " ")
		          .split("<%").join("\t")
		          .replace(/((^|%>)[^\t]*)'/g, "$1\r")
		          .replace(/\t=(.*?)%>/g, "',$1,'")
		          .split("\t").join("');")
		          .split("%>").join("p.push('")
		          .split("\r").join("\\'")
		      + "');}return p.join('');");
		   
		    // Provide some basic currying to the user
		    return data ? fn( data ) : fn;
		  };
}(api.templates = api.templates || {}, jQuery));
