// Tools
gui.configuration = new BasicGuiElement('Clear cache');
gui.configuration.link = function() {
    "use strict";
    api.templates.get('configuration', function(tmpl) {
        api.configuration.overview(function(data){
            gui.doLog(data);
            gui.clearWorkspace();
            gui.appendToWorkspace(api.templates.evaluate(tmpl, {
                config: data,
            }));
            gui.setLinksEvents();
            
            $('#form_config .form-control').each(function(i, element){
                $(element).attr('data-val', $(element).val());
            });
            
            // Add handlers to buttons
            $('#form_config .button-undo').on('click', function(event){
                var fld = $(this).attr('data-fld');
                gui.doLog(fld,$('#'+fld).val());
                $('#'+fld).val($('#'+fld).attr('data-val'));
            });
            
            $('#form_config .button-save').on('click', function(event){
                var cfg = {};
                $('#form_config .form-control').each(function(i, element){
                    var $element = $(element);
                    if( $element.attr('data-val') != $element.val()) {
                        var section = $element.attr('data-section');
                        var key = $element.attr('data-key');
                        if( cfg[section] === undefined ) {
                            cfg[section] = {};
                        }
                        cfg[section][key] = { value: $element.val() };
                    }
                });
                gui.doLog(cfg);
                if( !$.isEmptyObject(cfg) ) {
                    api.configuration.save(cfg, function(){
                        gui.showDashboard();
                        gui.notify(gettext('Configuration saved'), 'success');
                    }, gui.failRequestModalFnc);
                }
            });
        }, gui.failRequestModalFnc);
    });
};