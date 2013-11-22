/* jshint strict: true */
// -------------------------------
// Templates related
// Inserted into api
// for the admin app
// -------------------------------
(function(api, $) {
    "use strict";
    // Registers Handlebar useful helpers
    
    // Equal comparision (like if helper, but with comparation)
    Handlebars.registerHelper('ifequals', function(context1, context2, options) {
        console.log('Comparing ', context1, ' with ', context2);
        if(context1 == context2) {
            return options.fn(this);
        } else {
            return options.inverse(this);
        }
      });    
    
    
    api.templates = {};
    // Now initialize templates api
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

    // Simple JavaScript Templating, using HandleBars
    api.templates.evaluate = function(str, context) {
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
        var template = cached || Handlebars.compile(str);
        return context ? template(context) : template;
    };
}(window.api = window.api || {}, jQuery));
