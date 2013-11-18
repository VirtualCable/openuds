(function(tools, $, undefined) {
    tools.base64 = function(s) {
        return window.btoa(unescape(encodeURIComponent(s)));
    };
}(api.tools = api.tools || {}, jQuery));
