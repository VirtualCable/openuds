// To run this compressor, we need:
// nodejs (with npm ofc)
// node-minify (https://github.com/srod/node-minify) (npm install node-minify)



var compressor = require('node-minify');

var static_folder = process.argv[2] || '../uds/static/';

function minify_admin() {
    var jsFolder = static_folder + 'adm/js/';
    var cssFolder = static_folder + 'adm/css/';

    console.log('Minify admin from jsFolder ', jsFolder);
    
    var jsFiles = [
       // Tools
       'jquery.cookie',
       'bootstrap.min',
       'bootstrap-switch.min',
       'bootstrap-select.min',
       'jquery.validate.min',
       'jquery.blockUI',
       'jquery.flot.min',
       'jquery.dataTables.min',
       'TableTools.min',
       'Blob',
       'FileSaver',
       'ZeroClipboard',
       'dataTables.bootstrap',
       'handlebars-v1.1.2',
       // Api
       'api',
       'api-tools',
       'api-templates',
       'api-spreadsheet',
       // Gui
       'gui',
       'gui-tools',
       'gui-form',
       'gui-element',
       // Gui definition
       'gui-definition',
       'gui-d-dashboard',
       'gui-d-services',
       'gui-d-authenticators',
       'gui-d-osmanagers',
       'gui-d-connectivity',
       'gui-d-servicespools',
       'gui-d-config'
    ];
    
    var cssFiles = [
        'bootstrap.min',
        'font-awesome.min',
        'bootstrap-formhelpers.min',
        'bootstrap-switch',
        'bootstrap-select.min',
        'jquery.dataTables',
        'TableTools',
        'dataTables.bootstrap',
        'tables',
        'buttons',
        'uds-admin',
    ];
    
    var fileInJs = [];
    jsFiles.forEach(function(val, index, array){
        fileInJs.push( val + '.js' );
    });

    new compressor.minify({
        type: 'gcc',
        language: 'ECMASCRIPT5',
        publicFolder: jsFolder,
        fileIn: fileInJs,
        fileOut: jsFolder + 'admin.min.js',
        callback: function(err, min){
            console.log(err);
        }
    });

    var fileInCss = [];
    cssFiles.forEach(function(val, index, array){
        fileInCss.push( val + '.css' );
    });
    
 // Using Sqwish for CSS
    new compressor.minify({
        type: 'sqwish',
        publicFolder: cssFolder,
        fileIn: fileInCss,
        fileOut: cssFolder + 'admin.min.css',
        callback: function(err, min){
            console.log('Sqwish');
            console.log(err);
        }
    });
}

console.log('Starting minify of javascript');
minify_admin();