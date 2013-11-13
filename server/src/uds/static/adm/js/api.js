(function(api, $, undefined) {
	 
	// "private" methods
	api.doLog = function(data) {
		if( api.debug  ) {
			try {
				console.log(data);
			} catch (e) {
				// nothing can be logged
			}
			
		}
	}
	
	// "public" methods
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
	api.debug = true;
}(window.api = window.api || {}, jQuery));



// Service providers related
api.providers = (function($){
	var pub = {};
	
	pub.cached_types = undefined;
	
	pub.list = function(success_fnc) {
		api.getJson('providers',success_fnc);
	}
	
	pub.types = function(success_fnc) {
		// Cache types locally, will not change unless new broker version
		if( pub.cached_types ) {
			if( success_fnc ) {
				success_fnc(pub.cached_types);
			}
		}
		
		api.getJson('providers/types', function(data){
			pub.cached_types = data;
			if( success_fnc ) {
				success_fnc(pub.cached_types);
			}
		});
	}
	
	return pub;
}(jQuery)); 


// Service related
api.services = (function($){
	var pub = {};
	
	pub.get = function(success_fnc) {
		return api.getJson('/rest/providers', success_fnc);
	}
	return pub;
}(jQuery));