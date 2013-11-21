// -------------------------------
// Templates related
// Inserted into api
// for the admin app
// -------------------------------
(function(api, $) {
    api.templates = {};
    
    api.templates.cache = new api.cache('tmpls'); // Will cache templates locally. If name contains
                            // '?', data will not be cached and always
                            // re-requested. We do not care about lang, because page will reload on language change
    api.templates.get = function(name, success_fnc) {
        var $this = this;
        success_fnc = success_fnc || function(){};
        api.doLog('Getting tempkate ' + name);
        if (name.indexOf('?') == -1) {
            if ($this.cache.get(name) ) {
                success_fnc($this.cache.get(name));
                return;
             // Let's check if a "preloaded template" exists                
            } else if( document.getElementById('tmpl_' + name) ) { 
                $this.cache.put(name, 'tmpl_' + name); // In fact, this is not neccesary...
                success_fnc('tmpl_' + name);
                return;
            }
        }
        $.ajax({
            url : api.template_url + name,
            type : "GET",
            dataType : "text",
            success : function(data) {
                var cachedId = 'tmpl_' + name;
                $this.cache.put('_' + cachedId, $this.evaluate(data));
                $this.cache.put(name, cachedId);
                api.doLog('Success getting template "' + name + '".');
                api.doLog('Received: ' + data);
                success_fnc(cachedId);
            },
            fail: function( jqXHR, textStatus, errorThrown ) {
                api.doLog(jqXHR);
                api.doLog(textStatus);
                apid.doLog(errorThrown);
              },
            });
    };

    // Simple JavaScript Templating
    // Based on John Resig - http://ejohn.org/ - MIT Licensed
    api.templates.evaluate = function (str, data) {
        // Figure out if we're getting a template, or if we need to
        // load the template - and be sure to cache the result.
        var cached;
        if( !/\W/.test(str) ) {
            cached = this.cache.get('_'+str);
            if( cached === undefined ) {
                cached = api.templates.evaluate(document.getElementById(str).innerHTML);
                this.cache.put('_'+str, cached);
            }
            
        }
        // If cached, get cached first
        var fn =  cached ||
        // Generate a reusable function that will serve as a template
        // generator (and which will be cached).
        new Function("obj", "var p=[],print=function(){p.push.apply(p,arguments);};" +

                // Introduce the data as local variables using with(){}
                "with(obj){p.push('" +

                // Convert the template into pure JavaScript
                str.replace(/[\r\t\n]/g, " ").split("<%").join("\t").replace(/((^|%>)[^\t]*)'/g, "$1\r").replace(
                        /\t=(.*?)%>/g, "',$1,'").split("\t").join("');").split("%>").join("p.push('").split("\r").join(
                        "\\'") + "');}return p.join('');");

        // Provide some basic currying to the user
        return data ? fn(data) : fn;
    };
}(window.api = window.api || {}, jQuery));
