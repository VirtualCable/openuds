/* jshint strict: true */
(function(api, $, undefined) {
    "use strict";
    // "public" methods
    api.doLog = function(data) {
        if (api.debug) {
            try {
                console.log(data);
            } catch (e) {
                // nothing can be logged
            }

        }
    };
    
    // Cache table
    api.cacheTable = {};
    
    // Returns a cache object (for easy caching requests, templates, etc...)
    api.cache = function(cacheName) {
        return new Cache(cacheName);
    };
    
    api.cache.clear = function(cacheName) {
        if( cacheName === undefined ) {
            api.cacheTable = {};
        } else {
            api.cacheTable[cacheName] = {};
        }
    };
    
    api.getJson = function(path, options) {
        options = options || {};
        var success_fnc = options.success || function(){}; 
            
        var url = api.url_for(path);
        api.doLog('Ajax GET Json for "' + url + '"');
        $.ajax({
            url : url,
            type : "GET",
            dataType : "json",
            success : function(data) {
                api.doLog('Success on "' + url + '".');
                api.doLog('Received ' + JSON.stringify(data));
                success_fnc(data);
            },
            beforeSend : function(request) {
                request.setRequestHeader(api.auth_header, api.token);
            },
        });
    };

    // Public attributes
    api.debug = false;
}(window.api = window.api || {}, jQuery));


// Cache related
function Cache(cacheName) {
    "use strict";
    api.cacheTable[cacheName] = api.cacheTable[cacheName] || {};

    this.name = cacheName;
    this.cache = api.cacheTable[cacheName];
}

Cache.prototype = {
        get: function(key, not_found_fnc){
            "use strict";
            not_found_fnc = not_found_fnc || function() { return undefined; };
        
            if( this.cache[key] === undefined ) {
                this.cache[key] = not_found_fnc();
            }
            return this.cache[key];
        },
    
    put: function(key, value) {
        "use strict";
        this.cache[key] = value;
        },
};


// Great part of UDS REST api provides same methods.
// We will take advantage of this and save a lot of nonsense, prone to failure
// code :-)

function BasicModelRest(path, options) {
    "use strict";
    options = options || {};
    path = path || '';
    // Requests paths
    this.path = path;
    this.getPath = options.getPath || path;
    this.typesPath = options.typesPath || (path + '/types');
    this.tableInfoPath = options.tableInfoPath || (path + '/tableinfo');
    this.cache = api.cache('bmr'+path);
}

BasicModelRest.prototype = {
    // options:
    // cacheKey: '.' --> do not cache
    //           undefined -- > use path as key
    //           success: success fnc to execute in case of success
    _requestPath: function(path, options) {
        "use strict";
        options = options || {};
        var success_fnc = options.success || function(){api.doLog('success not provided for '+path);};
        var cacheKey = options.cacheKey || path;
        
        if( path == '.' ) {
            success_fnc({});
            return;
        }
        
        if (cacheKey != '.' && this.cache.get(cacheKey)) {
            success_fnc(this.cache.get(cacheKey));
        } else {
            var $this = this;
            api.getJson(path, { 
                success: function(data) {
                    if( cacheKey != '.' ) {
                        $this.cache.put(cacheKey, data);
                    }
                    success_fnc(data);
                },
            });
        }
    },
    get : function(options) {
        "use strict";
        options = options || {};
        
        var path = this.getPath;
        if (options.id !== undefined)
            path += '/' + options.id;
        return this._requestPath(path, {
            cacheKey: '.', // Right now, do not cache this
            success: options.success,
            
        });
    },
    types : function(options) {
        "use strict";
        options = options || {};
        return this._requestPath(this.typesPath, {
            cacheKey: 'type',
            success: options.success,
        });
    },
    gui: function(typeName, options) {
        // GUI returns a dict, that contains:
        // name: Name of the field
        // value: value of the field (selected element in choice, text for inputs, etc....)
        // gui: Description of the field (type, value or values, defvalue, ....
        "use strict";
        options = options || {};
        var path = [this.typesPath, typeName, 'gui'].join('/');
        return this._requestPath(path, {
            cacheKey: typeName + '-gui',
            success: options.success,
        });
    },
    tableInfo : function(options) {
        "use strict";
        options = options || {};
        var success_fnc = options.success || function(){api.doLog('success not provided for tableInfo');};
        
        var path = this.tableInfoPath;
        // Cache types locally, will not change unless new broker version
        if( this.cache.get(path) ) {
            if (success_fnc) {
                success_fnc(this.cache.get(path));
            }
            return;
        }

        var $this = this;
        api.getJson(path, {
            success: function(data) {
                        $this.cache.put(path, data);
                        success_fnc(data);
                    },
        });

    },
    
    detail: function(id, child) {
        "use strict";
        return new DetailModelRestApi(this, id, child);
    }

};

// For REST of type /auth/[id]/users, /services/[id]/users, ...
function DetailModelRestApi(parentApi, parentId, model) {
    "use strict";
    this.base = new BasicModelRest(undefined, {
        getPath: [parentApi.path, parentId, model].join('/'),
        typesPath: '.', // We do not has this on details
        tableInfoPath: [parentApi.path, 'tableinfo', parentId, model].join('/'),
    });
}

DetailModelRestApi.prototype = {
    // Generates a basic model with fixed methods for "detail" models
    get: function(options) {
        "use strict";
        return this.base.get(options);
    },
    types: function(options) {
        "use strict";
        return this.base.types(options);
    },
    tableInfo: function(options) { 
        "use strict";
        return this.base.tableInfo(options);
    },
};

// Populate api

api.providers = new BasicModelRest('providers');
// api.services = new BasicModelRest('services');
api.authenticators = new BasicModelRest('authenticators');

api.osmanagers = new BasicModelRest('osmanagers');
api.transports = new BasicModelRest('transports');
api.networks = new BasicModelRest('networks');

// Locale related
api.locale = new BasicModelRest('locale');
api.locale.tableInfo = api.locale.types = undefined;