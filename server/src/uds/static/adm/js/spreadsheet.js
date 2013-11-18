(function(spreadsheet, $, undefined) {
    spreadsheet.cell = function(data, type, style) {
        type = type || 'String';
        if( style !== undefined ) {
            style = ' ss:StyleID="' + style + '"';
        } else {
            style = '';
        }
        return '<Cell' + style + '><Data ss:Type="' + type + '">' + data + '</Data></Cell>';
    };
    
    spreadsheet.row = function(cell) {
        return '<Row>' + cell + '</Row>';
    };
}(api.spreadsheet = api.spreadsheet || {}, jQuery));
