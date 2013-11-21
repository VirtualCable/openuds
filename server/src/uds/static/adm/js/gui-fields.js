/* jshint strict: true */
(function(gui, $, undefined) {
    "use strict";

    // Returns a form that will manage a gui description (new or edit)
    gui.fields = function(item_description) {
        $.each(item_description, function(index, field){
           gui.doLog(field); 
        });
    };

    gui.fields.config = {
            text: {
                css: 'form-control'
                
            },
            textbox: {
                css: 'form-control'
            },
            numeric: {
                css: 'form-control'
            },
            password: {
                css: 'form-control'
            },
            hidden: {
                css: ''
            },
            choice: {
                css: ''
            },
            multichoice: {
                css: ''
            },
            editlist: {
                css: ''
            },
            checkbox: {
                css: 'form-control'
            },
    };
    
}(window.gui = window.gui || {}, jQuery));

