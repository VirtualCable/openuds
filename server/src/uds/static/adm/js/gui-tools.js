/* jshint strict: true */
(function(gui, $, undefined) {
    "use strict";
    
    gui.tools = {
        blockUI : function(message) {
            message = message || '<h1><span class="fa fa-spinner fa-spin"></span> ' + gettext('Just a moment...') + '</h1>';
            $.blockUI({ message: message });
        },
        unblockUI : function() {
            $.unblockUI();
            $('.DTTT_collection_background').remove();            
        },
        fix3dButtons : function(selector) {
            selector = selector || '';
            selector += ' .btn3d';
            console.log(selector);
            $.each($(selector), function(index, value) {
                var $this = $(this);
                
                var clkEvents = [];
                
                // Store old click events, so we can reconstruct click chain later
                $.each($._data(value, 'events').click, function(index, fnc) {
                    clkEvents.push(fnc);
                });
                $this.unbind('click');
                
                /* If Mousedown registers a temporal mouseUp event on parent, to lauch button click */ 
                $this.mousedown(function(event){
                    $('body').mouseup(function(e){
                        // Remove temporal mouseup handler
                        $(this).unbind('mouseup');
                        
                        // If movement of mouse is not too far... (16 px maybe well for 3d buttons?)
                        var x = event.pageX - e.pageX, y = event.pageY - e.pageY;
                        var dist_square = x*x + y*y;
                        if( dist_square < 16*16 ) {
                            // Register again old event handlers
                            $.each(clkEvents, function(index, fnc){
                                $this.click(fnc.handler);
                            });
                            $this.click();
                            $this.unbind('click');
                        }
                    });
                });
             });
        },
    };
    
}(window.gui = window.gui || {}, jQuery));