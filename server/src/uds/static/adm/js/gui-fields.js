/* jshint strict: true */
(function(gui, $, undefined) {
    "use strict";
    
    // Returns a form that will manage a gui description (new or edit)
    gui.fields = function(item_description) {
        $.each(item_description, function(index, field){
           gui.doLog(field); 
        });
    };
    
}(window.gui = window.gui || {}, jQuery));

gui.fields.options = {
        text: {
            css: 'form-control'
        },
        textbox: {
            
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