(function(api, $, undefined) {

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
    
    // Returns a cache object (for easy caching requests, templates, etc...)
    api.cache = function(cacheName) {
        return new Cache(cacheName);
    };
    
    api.getJson = function(path, success_fnc) {
        url = api.url_for(path);
        api.doLog('Ajax GET Json for "' + url + '"');
        $.ajax({
            url : url,
            type : "GET",
            dataType : "json",
            success : function(data) {
                api.doLog('Success on "' + url + '".');
                api.doLog('Received ' + JSON.stringify(data));
                if (success_fnc !== undefined) {
                    api.doLog('Executing success method');
                    success_fnc(data);
                }
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
    api.cacheTable = api.cacheTable || {};
    
    api.cacheTable[cacheName] = api.cacheTable[cacheName] || {};

    this.name = cacheName;
    this.cache = api.cacheTable[cacheName];
}

Cache.prototype = {
        get: function(key, not_found_fnc){
            not_found_fnc = not_found_fnc || function() { return undefined; };
        
            if( this.cache[key] === undefined ) {
                this.cache[key] = not_found_fnc();
            }
            return this.cache[key];
        },
    
    put: function(key, value) {
            this.cache[key] = value;
        },
};


// Great part of UDS REST api provides same methods.
// We will take advantage of this and save a lot of nonsense, prone to failure
// code :-)

function BasicModelRest(path, options) {
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
    get : function(options) {
        options = options || {};
        
        var path = this.getPath;
        if (options.id !== undefined)
            path += '/' + options.id;
        api.getJson(path, options.success);
    },
    types : function(success_fnc) {
        // Cache types locally, will not change unless new broker version
        sucess_fnc = success_fnc || function(data){};
        if( this.typesPath == '.' ) {
            success_fnc({});
            return;
        }
        if (this.cache.get('types')) {
            success_fnc(this.cache.get('types'));
        } else {
            var $this = this;
            var path = this.typesPath;
            api.getJson(path, function(data) {
                $this.cache.put('types', data);
                success_fnc(data);
            });
        }
    },

    tableInfo : function(success_fnc) {
        var path = this.tableInfoPath;
        // Cache types locally, will not change unless new broker version
        if( this.cache.get(path) ) {
            if (success_fnc) {
                success_fnc(this.cache.get(path));
            }
            return;
        }

        var $this = this;
        api.getJson(path, function(data) {
            $this.cache.put(path, data);
            success_fnc(data);
        });

    },
    
    detail: function(id, child) {
        return new DetailModelRestApi(this, id, child);
    }

};

// For REST of type /auth/[id]/users, /services/[id]/users, ...
function DetailModelRestApi(parentApi, parentId, model) {
    this.base = new BasicModelRest(undefined, {
        getPath: [parentApi.path, parentId, model].join('/'),
        typesPath: '.', // We do not has this on details
        tableInfoPath: [parentApi.path, 'tableinfo', parentId, model].join('/'),
    });
}

DetailModelRestApi.prototype = {
    // Generates a basic model with fixed methods for "detail" models
    get: function(options) {
        return this.base.get(options);
    },
    types: function(success_fnc) {
        return this.base.types(success_fnc);
    },
    tableInfo: function(success_fnc) { 
        return this.base.tableInfo(success_fnc);
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