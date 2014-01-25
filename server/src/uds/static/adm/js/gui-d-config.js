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
            
        }, gui.failRequestModalFnc);
    });
};