/* jshint strict: true */
(function(gui, $, undefined) {
    "use strict";

    gui.forms = {};

    // Returns form fields that will manage a gui description (new or edit)
    gui.forms.fieldsToHtml = function(itemGui, item, editing) {
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
    
    gui.forms.fromFields = function(fields, item) {
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
               tabsContent.push('<div class="tab-pane fade' + active + '" id="' + id + index + '">' + gui.forms.fieldsToHtml(tab.fields, item)  + '</div>' );
               tabs.push('<li><a href="#' + id + index + '" data-toggle="tab">' + tab.title + '</a></li>' );
               active = '';
            });
            form += '<ul class="nav nav-tabs">' + tabs.join('\n') + '</ul><div class="tab-content">' + tabsContent.join('\n') + '</div>';
        } else {
            form += gui.forms.fieldsToHtml(fields, item, editing);
        } 
        form += '</form>';
        return form;
    };

    // Reads fields from a form
    gui.forms.read = function(formSelector) {
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

    gui.forms.launchModal = function(title, fields, item, onSuccess) {
        var id = 'modal-' + Math.random().toString().split('.')[1]; // Get a random ID for this modal
        gui.appendToWorkspace(gui.modal(id, title, gui.forms.fromFields(fields, item)));
        id = '#' + id; // for jQuery
        
        // Get form
        var $form = $(id + ' form'); 
        
        // For "beauty" switches, initialize them now
        $(id + ' .make-switch').bootstrapSwitch();
        // Activate "cool" selects
        $(id + ' .selectpicker').selectpicker();
        // TEST: cooller on mobile devices
        if( /Android|webOS|iPhone|iPad|iPod|BlackBerry/i.test(navigator.userAgent) ) {
            $(id + ' .selectpicker').selectpicker('mobile');
        }
        // Activate tooltips
        $(id + ' [data-toggle="tooltip"]').tooltip({delay: {show: 1000, hide: 100}, placement: 'auto right'});
        
        // Validation
        $form.validate({
            debug: true,
            errorClass: 'text-danger',
            validClass: 'has-success',
            highlight: function(element) {
                $(element).closest('.form-group').addClass('has-error');
            },
            success: function(element) {
                $(element).closest('.form-group').removeClass('has-error');
                $(element).remove();
            },
        }); 
        
        // And catch "accept" (default is "Save" in fact) button click
        $(id + ' .button-accept').click(function(){
            if( !$form.valid() )
                return;
            if( onSuccess ) {
                onSuccess(id + ' form', function(){$(id).modal('hide');}); // Delegate close to to onSuccess  
                    return;
            } else {
                $(id).modal('hide');
            }
            
        });
        
        // Launch modal
        $(id).modal({keyboard: false})
             .on('hidden.bs.modal', function () {
                 $(id).remove();
             });
    };
    
    // simple gui generators
    gui.forms.guiField = function(name, type, label, tooltip, value, values, length, multiline, readonly, required) {
        length = length || 128;
        multiline = multiline !== undefined ? multiline : 0;
        readonly = readonly || false;
        required = required || false;
        return {
            name: name,
            gui: {
                defvalue: value,
                value: value,
                values: values,
                label: label,
                length: length,
                multiline: multiline,
                rdonly: readonly, // rdonly applies just to editing
                required: required,
                tooltip: tooltip,
                type: type,
            }
        };
    };
    
    
}(window.gui = window.gui || {}, jQuery));

