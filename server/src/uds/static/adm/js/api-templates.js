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
    // Use as block as {{#ifequals [element] [element]}}....{{/ifequals}}
    Handlebars.registerHelper('ifequals', function(context1, context2, options) {
        if(context1 == context2) {
            return options.fn(this);
        } else {
            return options.inverse(this);
        }
      });    

    // Belongs comparision (similar to "if xxx in yyyyy")
    // Use as block as {{#ifbelong [element] [group]}}....{{/ifbelongs}}
    Handlebars.registerHelper('ifbelongs', function(context1, context2, options) {
        gui.doLog('belongs', context1, context2);
        if($.inArray(context1, context2) != -1) {
            gui.doLog('belongs is true');
            return options.fn(this);
        } else {
            return options.inverse(this);
        }
      });    
    
    // Counters. 
    // Create a counter with {{counter [id] [startValue]}}
    // increment the counter with {{inc_counter [id]}}
    // get the counter value tiwh {{get_counter [id}}
    // Values are stored on current 
    Handlebars.registerHelper('set_counter', function(id, value, options){
        options.data['_counter_'+id] = value;
    });
    
    Handlebars.registerHelper('get_counter', function(id, options){
        return options.data['_counter_'+id];
    });
    
    Handlebars.registerHelper('inc_counter', function(id, options){
        options.data['_counter_'+id] += 1;
    });
    
    // For inserting "inline" javascript scripts, due to the fact that we cannot
    // Insert "<script>...</script>" inside inline elements (they are already scripts)
    Handlebars.registerHelper('javascript', function(options) {
        return new Handlebars.SafeString('<script>' + options.fn(this) + '</script>');
    });
    
    // Truncate chars, like django "truncatechars" filter
    Handlebars.registerHelper('truncatechars', function(len, value) {
        var val = value.toString(); // For Array objects, the toString method joins the array and returns one string containing each array element separated by commas
        if(val.length > len) {
            return val.substring(0, len-3) + "...";
        } else {
            return val;
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
        api.doLog('Getting template ' + name);
        if (name.indexOf('?') == -1) {
            if ($this.cache.get(name+'------') ) {
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
            url : api.url_for(name,'template'),
            type : "GET",
            dataType : "text",
            success : function(data) { 
                var cachedId = 'tmpl_' + name;
                $this.cache.put('_' + cachedId, $this.evaluate(data));
                $this.cache.put(name, cachedId);
                api.doLog('Success getting template "' + name + '".');
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
        // load the template - and be sure to cache the result (compiled template).
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
