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
				api.doLog(gettext('Success on "') + url + '".');
				api.doLog(gettext('Received ') + JSON.stringify(data));
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
		get: function(options) {
			if( options == undefined ){
				options = {};
			}
			var path = this.path;
			if( options.id != undefined )
				path += '/' + options.id;
			api.getJson(path, options.success);
		},
		types: function(success_fnc) {
			// Cache types locally, will not change unless new broker version
			if( this.cached_types ) {
				if( success_fnc ) {
					success_fnc(this.cached_types);
				}
			}
			else {
				var $this = this;
				
				api.getJson( this.path + '/types', function(data) {
					$this.cached_types = data;
					if( success_fnc ) {
						success_fnc($this.cached_types);
					}
				});
			}
		},
		
		tableInfo: function(success_fnc) {
			// Cache types locally, will not change unless new broker version
			if( this.cached_tableInfo ) {
				if( success_fnc ) {
					success_fnc(this.cached_tableInfo);
				}
				return;
			}
			var $this = this;
			
			api.getJson( this.path + '/tableinfo', function(data) {
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
		detail: function(parentId) {
			var rest = new BasicModelRest(this.parentPath + '/' + parentId + '/' + this.path);
			rest.types = function() {
				return []; // No types at all
			}
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