(function(api, $, undefined) {
    
    api.cache = function(cacheName) {
        return new Cache(cacheName);
    };

}(window.api = window.api || {}, jQuery));

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