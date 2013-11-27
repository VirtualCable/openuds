/* jshint strict: true */
(function(gui, $, undefined) {
    "use strict";

    // Returns a form that will manage a gui description (new or edit)
    gui.fieldsToHtml = function(itemGui, item, editing) {
        var html = '';
        // itemGui is expected to have fields sorted by .gui.order (REST api returns them sorted)
        $.each(itemGui, function(index, f){
            gui.doLog(f);
            gui.doLog(item[f.name]);
            // Fix multiline text fields to textbox
            if( f.gui.type == 'text' && f.gui.multiline ) {
                f.gui.type = 'textbox';
            }
            html += api.templates.evaluate('tmpl_fld_'+f.gui.type, {
                value: item[f.name] || f.gui.value || f.gui.defvalue, // If no value present, use default value
                values: f.gui.values,
                label: f.gui.label,
                length: f.gui.length,
                multiline: f.gui.multiline,
                readonly: editing ? f.gui.rdonly : false, // rdonly applies just to editing
                required: f.gui.required,
                tooltip: f.gui.tooltip,
                type: f.gui.type,
                name: f.name,
                css: 'modal_field_data',
            });
        });
        return html;
    };
    
    gui.form = {};
    
    gui.form.fromFields = function(fields, item) {
        var editing = item !== undefined; // Locate real Editing
        item = item || {id:''};
        var form = '<form class="form-horizontal" role="form">' +
                   '<input type="hidden" name="id" class="modal_field_data" value="' + item.id + '">';
        if( fields.tabs ) {
            var id = 'tab-' + Math.random().toString().split('.')[1]; // Get a random base ID for tab entries
            var tabs = [];
            var tabsContent = [];
            var active = ' active in' ;
            $.each(fields.tabs, function(index, tab){
               tabsContent.push('<div class="tab-pane fade' + active + '" id="' + id + index + '">' + gui.fieldsToHtml(tab.fields, item)  + '</div>' );
               tabs.push('<li><a href="#' + id + index + '" data-toggle="tab">' + tab.title + '</a></li>' );
               active = '';
            });
            form += '<ul class="nav nav-tabs">' + tabs.join('\n') + '</ul><div class="tab-content">' + tabsContent.join('\n') + '</div>';
        } else {
            form += gui.fieldsToHtml(fields, item, editing);
        } 
        form += '</form>';
        return form;
    };

    // Reads fields from a form
    gui.form.read = function(formSelector) {
        var res = {};
        $(formSelector + ' .modal_field_data').each(function(i, field) {
            var $field = $(field);
            if( $field.attr('name') ) { // Is a valid field
                if( $field.attr('type') == 'checkbox') {
                    res[$field.attr('name')] = $field.is(':checked');
                } else {
                    res[$field.attr('name')] = $field.val();
                }
            }
        });
        gui.doLog(res);
        return res;
    };

    
}(window.gui = window.gui || {}, jQuery));

