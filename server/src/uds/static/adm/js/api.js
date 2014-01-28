/* jshint strict: true */
(function(api, $, undefined) {
    "use strict";
    // "public" methods
    api.doLog = function() {
        if (api.debug) {
            try {
                console.log.apply(window, arguments);
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
    
    api.url_for = function(path, type) {
        switch(type) {
            case 'template':
                return api.config.template_url + path;
            case undefined:
            case 'rest':
                return api.config.base_url + path;
            default:
                throw new Exception('Type of url not found: ' + type);
        }
    };
    
    // Default fail function
    api.defaultFail = function(jqXHR, textStatus, errorThrown) {
        api.doLog(jqXHR, ', ', textStatus, ', ', errorThrown);
    };
    
    api.getJson = function(path, options) {
        options = options || {};
        var success_fnc = options.success || function(){};
        var fail_fnc = options.fail || api.defaultFail;
            
        var url = api.url_for(path);
        api.doLog('Ajax GET Json for "' + url + '"');
        $.ajax({
            url : url,
            type : options.method || "GET", // Will use GET if no method provided
            dataType : "json",
            success : function(data) {
                api.doLog('Success on GET "' + url + '".');
                api.doLog('Received ', data);
                success_fnc(data);
            },
            error: function(jqXHR, textStatus, errorThrown) {
                api.doLog('Error on GET "' + url + '". ', textStatus, ', ', errorThrown);
                fail_fnc(jqXHR, textStatus, errorThrown);
            },
            beforeSend : function(request) {
                request.setRequestHeader(api.config.auth_header, api.config.token);
            },
        });
    };
    
    api.putJson = function(path, data, options) {
        options = options || {};
        var success_fnc = options.success || function(){}; 
        var fail_fnc = options.fail || api.defaultFail;
            
        var url = api.url_for(path);
        api.doLog('Ajax PUT Json for "' + url + '"');
        $.ajax({
            url : url,
            type : options.method || "PUT", // Will use PUT if no method provided 
            dataType : "json",
            data: JSON.stringify(data),
            success: function(data) {
                api.doLog('Success on PUT "' + url + '".');
                api.doLog('Received ', data);
                success_fnc(data);
            },
            error: function(jqXHR, textStatus, errorThrown) {
                api.doLog('Error on PUT "' + url + '". ', textStatus, ', ', errorThrown);
                fail_fnc(jqXHR, textStatus, errorThrown);
            },
            beforeSend : function(request) {
                request.setRequestHeader(api.config.auth_header, api.config.token);
            },
        });
    };  // End putJson
    

    api.deleteJson = function(path, options) {
        options = options || {};
        var success_fnc = options.success || function(){}; 
        var fail_fnc = options.fail || api.defaultFail;
            
        var url = api.url_for(path);
        api.doLog('Ajax DELETE Json for "' + url + '"');
        $.ajax({
            url : url,
            type : "DELETE",
            dataType : "json",
            success: function(data) {
                api.doLog('Success on DELETE "' + url + '".');
                api.doLog('Received ', data);
                success_fnc(data);
            },
            error: function(jqXHR, textStatus, errorThrown) {
                api.doLog('Error on DELETE "' + url + '". ', textStatus, ', ', errorThrown);
                fail_fnc(jqXHR, textStatus, errorThrown);
            },
            beforeSend : function(request) {
                request.setRequestHeader(api.config.auth_header, api.config.token);
            },
        });
    };  // End putJson
    

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
    this.logPath = options.logPath || path;
    this.putPath = options.putPath || path;
    this.testPath = options.testPath || (path + '/test');
    this.delPath = options.delPath || path;
    this.typesPath = options.typesPath || (path + '/types');
    this.guiPath = options.guiPath || (path + '/gui');
    this.tableInfoPath = options.tableInfoPath || (path + '/tableinfo');
    this.cache = api.cache('bmr'+path);
}

BasicModelRest.prototype = {
    // options:
    // cacheKey: '.' --> do not cache (undefined will set cacheKey to current path)
    //           undefined -- > use path as key
    //           success: success fnc to execute in case of success
    _requestPath: function(path, options) {
        "use strict";
        options = options || {};
        var success_fnc = options.success || function(){api.doLog('success function not provided for '+path);};
        var fail_fnc = options.fail;
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
                fail: fail_fnc,
            });
        }
    },
    get: function(options) {
        "use strict";
        options = options || {};
        
        var path = this.getPath;
        if ( options.id )
            path += '/' + options.id;
        return this._requestPath(path, {
            cacheKey: '.', // Right now, do not cache any "get" method
            success: options.success,
            fail: options.fail
            
        });
    },
    list: function(success_fnc, fail_fnc) {  // This is "almost" an alias for get
        "use strict";
        return this.get({
            id: '',
            success: success_fnc,
            fail: fail_fnc
        });
    },
    overview: function(success_fnc, fail_fnc) {
        "use strict";
        return this.get({
            id: 'overview',
            success: success_fnc,
            fail: fail_fnc
        });
    },
    item: function(itemId, success_fnc, fail_fnc) {
        "use strict";
        return this.get({
            id: itemId,
            success: success_fnc,
            fail: fail_fnc
        });
        
    },
    // -------------
    // Log methods
    // -------------
    getLogs: function(itemId, success_fnc, fail_fnc) {
        "use strict";
        var path = this.logPath + '/' + itemId + '/' + 'log';
        return this._requestPath(path, {
            cacheKey: '.',
            success: success_fnc,
            fail: fail_fnc
        });
        
    },
    
    // -------------
    // Put methods
    // -------------
    
    put: function(data, options) {
        "use strict";
        options = options || {};
        
        var path = this.putPath;
        if ( options.id )
            path += '/' + options.id;
        
        api.putJson(path, data, {
           success:  options.success,
           fail: options.fail
        });
    },
    create: function(data, success_fnc, fail_fnc) {
      "use strict";
      
      return this.put(data, {
         success: success_fnc,
         fail: fail_fnc
      });
    },
    save: function(data, success_fnc, fail_fnc) {
        "use strict";  

        return this.put(data, {
            id: data.id,
            success: success_fnc,
            fail: fail_fnc
         });
    },
    
    // Testing
    test: function(type, data, success_fnc, fail_fnc) {
        "use strict";
        
        var path = this.testPath + '/' + type;
        
        api.putJson(path, data, {
           success:  success_fnc,
           fail: fail_fnc,
           method: 'POST'
        });
    },
    // --------------
    // Delete
    // --------------
    del: function(id, success_fnc, fail_fnc) {
        "use strict";
        
        var path = this.delPath + '/' + id;
        
        api.deleteJson(path, {
           success:  success_fnc,
           fail: fail_fnc
        });
    },
    
    // --------------
    // Types methods
    // --------------
    types : function(success_fnc, fail_fnc) {
        "use strict";
        return this._requestPath(this.typesPath, {
            cacheKey: this.typesPath,
            success: success_fnc,
        });
    },
    gui: function(typeName, success_fnc, fail_fnc) {
        // GUI returns a dict, that contains:
        // name: Name of the field
        // value: value of the field (selected element in choice, text for inputs, etc....)
        // gui: Description of the field (type, value or values, defvalue, ....
        "use strict";
        
        var path;
        if( typeName !== undefined ) {
            path = [this.guiPath, typeName].join('/');
        } else {
            path = this.guiPath;
        }
        return this._requestPath(path, {
            cacheKey: '.', // Gui is not cacheable, it's dynamic and can change from call to call
            success: success_fnc,
            fail: fail_fnc,
        });
    },
    tableInfo : function(success_fnc, fail_fnc) {
        "use strict";
        success_fnc = success_fnc || function(){api.doLog('success not provided for tableInfo');};
        
        var path = this.tableInfoPath;
        this._requestPath(path, {
            success: success_fnc,
            fail: fail_fnc,
        });
    },
    
    detail: function(id, child, options) {
        "use strict";
        options = options || {};
        return new DetailModelRestApi(this, id, child, options);
    }

};

// For REST of type /auth/[id]/users, /services/[id]/users, ...
function DetailModelRestApi(parentApi, parentId, model, options) {
    "use strict";
    this.options = options;
    this.base = new BasicModelRest([parentApi.path, parentId, model].join('/'));
}

DetailModelRestApi.prototype = {
    // Generates a basic model with fixed methods for "detail" models
    get: function(success_fnc, fail_fnc) {
        "use strict";
        return this.base.get(success_fnc, fail_fnc);
    },
    list: function(success_fnc, fail_fnc) {  // This is "almost" an alias for get
        "use strict";
        return this.base.list(success_fnc, fail_fnc);
    },
    overview: function(success_fnc, fail_fnc) {
        "use strict";
        return this.base.overview(success_fnc, fail_fnc);
    },
    item: function(itemId, success_fnc, fail_fnc) {
        "use strict";
        return this.base.item(itemId, success_fnc, fail_fnc);
    },
    // -------------
    // Log methods
    // -------------
    getLogs: function(itemId, success_fnc, fail_fnc) {
        "use strict";
        return this.base.getLogs(itemId, success_fnc, fail_fnc);
    },
    // Put methods
    put: function(data, options) {
        "use strict";
        return this.base.put(data, options);
    },
    create: function(data, success_fnc, fail_fnc) {
      "use strict";
      
      return this.put(data, {
         success: success_fnc,
         fail: fail_fnc
      });
    },
    save: function(data, success_fnc, fail_fnc) {
        "use strict";  

        return this.put(data, {
            id: data.id,
            success: success_fnc,
            fail: fail_fnc
         });
    },
    // Testing
    test: function(type, data, success_fnc, fail_fnc) {
        "use strict";  

        return this.base.test(type, data, success_fnc, fail_fnc);
    },
    // --------------
    // Delete
    // --------------
    del: function(id, success_fnc, fail_fnc) {
        "use strict";
        return this.base.del(id, success_fnc, fail_fnc);
    },
    
    tableInfo: function(success_fnc, fail_fnc) { 
        "use strict";
        return this.base.tableInfo(success_fnc, fail_fnc);
    },
    types: function(success_fnc, fail_fnc) {
        "use strict";
        if( this.options.types ) {
          this.options.types(success_fnc, fail_fnc);   
        } else {
            return this.base.types(success_fnc, fail_fnc);
        }
    },
    gui: function(typeName, success_fnc, fail_fnc) { // Typename can be "undefined" to request MAIN gui (it it exists ofc..)
        "use strict";
        return this.base.gui(typeName, success_fnc, fail_fnc);
    },
    
    // Generic "Invoke" method (with no args, if needed, put them on "method" after "?" as normal url would be
    invoke: function(method, success_fnc, fail_fnc) {
        "use strict";
        return this.base.get({
            id: method,
            success: success_fnc,
            fail: fail_fnc
        });
    },
    
};

// Populate api

api.providers = new BasicModelRest('providers');
// all services method used in providers
api.providers.allServices = function(success_fnc, fail_fnc) {
    "use strict";
    return this.get({
        id: 'allservices',
        success: success_fnc,
        fail: fail_fnc
    });
};


api.authenticators = new BasicModelRest('authenticators');
// Search method used in authenticators
api.authenticators.search = function(id, type, term, success_fnc, fail_fnc) {
    "use strict";
    return this.get({
        id: id + '/search?type=' + encodeURIComponent(type) + '&term=' + encodeURIComponent(term),
        success: success_fnc,
        fail: fail_fnc
    });
};

api.osmanagers = new BasicModelRest('osmanagers');
api.transports = new BasicModelRest('transports');
api.networks = new BasicModelRest('networks');
api.servicesPool = new BasicModelRest('servicespool');

api.configuration = new BasicModelRest('config');
api.system = new BasicModelRest('system');
