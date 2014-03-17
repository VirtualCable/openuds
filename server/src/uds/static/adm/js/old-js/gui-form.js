/* jshint strict: true */
(function(gui, $, undefined) {
    "use strict";

    gui.forms = {};

    gui.forms.callback = function(formSelector, method, params, success_fnc) {
        var path = 'gui/callback/' + method;
        var p = [];
        $.each(params, function(index, val) {
            p.push(val.name + '=' + encodeURIComponent(val.value));
        });
        path = path + '?' + p.join('&');
        api.getJson(path, {
            success: success_fnc,
        });
        
    };
    
    // Returns form fields that will manage a gui description (new or edit)
    gui.forms.fieldsToHtml = function(itemGui, item, editing) {
        var html = '';
        var fillers = []; // Fillers (callbacks)
        var originalValues = {}; // Initial stored values (defaults to "reset" form and also used on fillers callback to try to restore previous value)
        // itemGui is expected to have fields sorted by .gui.order (REST api returns them sorted)
        $.each(itemGui, function(index, f){
            if( f.gui === undefined ) { // Not exactly a field, maybe some other info...
                return;
            }
            // Fix multiline text fields to textbox
            if( f.gui.type == 'text' && f.gui.multiline ) {
                f.gui.type = 'textbox';
            }
            var value = item[f.name] || f.gui.value || f.gui.defvalue;
            // We need to convert "array" values for multichoices to single list of ids (much more usable right here)
            if( f.gui.type == 'multichoice') {
                var newValue = [];
                $.each(value, function(undefined, val) {
                   newValue.push(val.id); 
                });
                value = newValue;
            }
            
            originalValues[f.name] = value; // Store original value
            html += api.templates.evaluate('tmpl_fld_'+f.gui.type, {
                value: value, // If no value present, use default value
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
            
            // if this field has a filler (callback to get data)
            if( f.gui.fills ) {
                gui.doLog('This field has a filler');
                fillers.push({ name: f.name, callbackName: f.gui.fills.callbackName, parameters: f.gui.fills.parameters });
            }
            
        });
        return { html: html, fillers: fillers, originalValues: originalValues };
    };
    
    gui.forms.fromFields = function(fields, item) {
        var editing = item !== undefined; // Locate real Editing
        item = item || {id:''};
       
        var form = '<form class="form-horizontal" role="form">' +
                   '<input type="hidden" name="id" class="modal_field_data" value="' + item.id + '">';
        var fillers = [];
        var originalValues = {};
        
        if( fields.tabs ) {
            var id = 'tab-' + Math.random().toString().split('.')[1]; // Get a random base ID for tab entries
            var tabs = [];
            var tabsContent = [];
            var active = ' active in' ;
            $.each(fields.tabs, function(index, tab){
               var h = gui.forms.fieldsToHtml(tab.fields, item);
               tabsContent.push('<div class="tab-pane fade' + active + '" id="' + id + index + '">' + h.html + '</div>' );
               tabs.push('<li><a href="#' + id + index + '" data-toggle="tab">' + tab.title + '</a></li>' );
               active = '';
               fillers = fillers.concat(h.fillers); // Fillers (callback based)
               $.extend(originalValues, h.originalValues); // Original values
               gui.doLog('Fillers:', h.fillers);
            });
            form += '<ul class="nav nav-tabs">' + tabs.join('\n') + '</ul><div class="tab-content">' + tabsContent.join('\n') + '</div>';
        } else {
            var h = gui.forms.fieldsToHtml(fields, item, editing);
            form += h.html;
            fillers = fillers.concat(h.fillers);
            $.extend(originalValues, h.originalValues);
        } 
        form += '</form>';
        
        gui.doLog('Original values: ', originalValues);
        
        // Init function for callbacks.
        // Callbacks can only be attached to "Selects", but it's parameters can be got from any field
        // This needs the "form selector" as base for setting callbacks, etc..
        var init = function(formSelector) {
            gui.doLog(formSelector, fillers);
            
            var onChange = function(filler) {
                return function() {
                    gui.doLog('Onchange invoked for ', filler);
                    // Attach on change method to each filler, and after that, all 
                    var params = [];
                    $.each(filler.parameters, function(undefined, p){
                        var val = $(formSelector + ' [name="' + p + '"]').val();
                        params.push({name: p, value: val});
                    });
                    gui.forms.callback(formSelector, filler.callbackName, params, function(data){
                        $.each(data, function(undefined, sel){
                            // Update select contents with returned values
                            var $select = $(formSelector + ' [name="' + sel.name + '"]');
                            
                            $select.empty();
                            $.each(sel.values, function(undefined, value){
                                $select.append('<option value="' + value.id + '">' + value.text + '</option>');
                            });
                            $select.val(originalValues[sel.name]);
                            // Refresh selectpicker if item is such
                            if($select.hasClass('selectpicker'))
                                $select.selectpicker('refresh');
                            // Trigger change for the changed item
                            $select.trigger('change');
                            
                        });
                    });
                };
            };
            
            // Sets the "on change" event for select with fillers (callbacks that fills other fields)
            $.each(fillers, function(undefined, f) {
                $(formSelector + ' [name="' + f.name + '"]').on('change', onChange(f));
            });

            // Trigger first filler if it exists, this will cascade rest of "changes" if they exists
            if( fillers.length )
                $(formSelector + ' [name="' + fillers[0].name + '"]').trigger('change');
        };
        
        return { 'html': form, 'init': init }; // Returns the form and a initialization function for the form, that must be invoked to start it
    };

    // Reads fields from a form
    gui.forms.read = function(formSelector) {
        var res = {};
        $(formSelector + ' .modal_field_data').each(function(i, field) {
            var $field = $(field);
            if( $field.attr('name') ) { // Is a valid field
                var name = $field.attr('name');
                if( $field.attr('type') == 'checkbox') {
                    res[name] = $field.is(':checked');
                } else {
                    res[name] = $field.val();
                    if( res[name] === null && $field.is('select') )
                        res[name] = [];
                }
            }
        });
        gui.doLog(res);
        return res;
    };
    
    // Options has this keys:
    //   title
    //   fields
    //   item
    //   success
    //   buttons: Array of buttons to be added to footer, with:
    //            text --> text of button
    //            css  --> button style (btn-default, btn-warning, ...). If not defined, 'btn-default' will be used
    //            action --> function to be executed. Will be passed 3 parameters: event, formSelector and closeFnc
    //                       (use gui.forms.read(form selector) to get fields, closeFnc() to close form if desired)
    // Failed operations will show a modal with server error
    gui.forms.launchModal = function(options, onSuccess) {
        options = options || {};
        
        var id = 'modal-' + Math.random().toString().split('.')[1]; // Get a random ID for this modal
        var ff = gui.forms.fromFields(options.fields, options.item);
        var footer = '';
        var clickEventHandlers = [];
        
        if( options.buttons ) {
            $.each(options.buttons, function(index, value){
                var _id = id + '-footer-' + index;
                var css = value.css || 'btn-default';
                clickEventHandlers.push({id: '#' + _id, action: value.action });
                footer +=  '<button id="' + _id + '" type="button" class="pull-left btn ' + css + '">' + value.text + '</button>';
            });
        }
        gui.appendToWorkspace(gui.modal(id, options.title, ff.html, { footer: footer }));
        id = '#' + id; // for jQuery
        
        var formSelector = id + ' form';
        var closeFnc = function(){$(id).modal('hide');};
        
        if( ff.init )
            ff.init(id);
        
        // Append click events for custom buttons on footer
        $.each(clickEventHandlers, function(undefined, value){
            if( value.action ) {
                $(value.id).on('click', function(event){
                    value.action(event, formSelector, closeFnc);
                });
            }
        });
        
        // Get form
        var $form = $(id + ' form'); 
        
        gui.tools.applyCustoms(id);
        
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
            if( options.success ) {
                options.success(formSelector, closeFnc); // Delegate close to to onSuccess  
                    return;
            } else {
                closeFnc();
            }
            
        });
        
        // If preprocessors of modal (maybe custom event handlers)
        if( options.preprocessor ) {
            options.preprocessor(id);
        }
        
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

