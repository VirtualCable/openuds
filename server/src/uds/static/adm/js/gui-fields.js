/* jshint strict: true */
(function(gui, $, undefined) {
    "use strict";

    // Returns a form that will manage a gui description (new or edit)
    gui.fields = function(item_description) {
        var form = '<form class="form-horizontal" role="form">';
        // item_description is expected to have fields sorted by .gui.order (REST api returns them sorted)
        $.each(item_description, function(index, f){
            
            gui.doLog(f);
            var editing = false; // Locate real Editing
            form += api.templates.evaluate('tmpl_fld_'+f.gui.type, {
                value: f.value || f.gui.value || f.gui.defvalue, // If no value present, use default value
                values: f.gui.values,
                label: f.gui.label,
                length: f.gui.length,
                multiline: f.gui.multiline,
                rdonly: editing ? f.gui.rdonly : false, // rdonly applies just to editing
                required: f.gui.required,
                tooltip: f.gui.tooltip,
                type: f.gui.type,
                name: f.name,
            });
        });
        form += '</form>';
        return form;
    };

}(window.gui = window.gui || {}, jQuery));

