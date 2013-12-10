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
                // If no events associated, return
                if( $._data(value, 'events') === undefined )
                    return;

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
        applyCustoms: function(selector) {
            // Activate "custom" styles
            $(selector + ' .make-switch').bootstrapSwitch();
            // Activate "cool" selects
            $(selector + ' .selectpicker').selectpicker();
            // TEST: cooler on mobile devices
            if( /Android|webOS|iPhone|iPad|iPod|BlackBerry/i.test(navigator.userAgent) ) {
                $(selector + ' .selectpicker').selectpicker('mobile');
            }
            // Activate tooltips
            $(selector + ' [data-toggle="tooltip"]').tooltip({delay: {show: 1000, hide: 100}, placement: 'auto right'});
            
            // Fix 3d buttons
            gui.tools.fix3dButtons(selector);
        },
        // Datetime renderer (with specified format)
        renderDate : function(format) {
            return function(data, type, full) {
                return api.tools.strftime(format, new Date(data*1000));
            };
        },
        // Log level rendererer
        renderLogLovel : function() {
            var levels = {
                    10000 : 'OTHER',
                    20000 : 'DEBUG',
                    30000 : 'INFO',
                    40000 : 'WARN',
                    50000 : 'ERROR',
                    60000 : 'FATAL'
            };
            
            return function(data, type, full) {
                return levels[data] || 'OTHER';
            }
        },

    };
    
}(window.gui = window.gui || {}, jQuery));