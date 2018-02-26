/// <reference path="uds/API.ts" />
/// <reference path="uds/params.ts" />

namespace uds {
    var udsClientApp = angular.module('udsClientApp', []);

    class LoginController {
        selected: Authenticator;
        authenticators: Authenticator[];
        api : API;

        // Order is important!!, must mucht those on constructor
        // This tells angular the requred services, etc... to be passed to constructor
        static $inject = ["$http", "$q"];

        constructor(
            private $http: ng.IHttpService,
            private $q: ng.IQService
        ) {
            this.selected = null;
            this.authenticators = [];
            this.api = new API($http, $q);

            this.api.getAuthenticators().then((data) => {
                this.authenticators = data;
                if (data.length > 0)
                    this.selected = data[0];
                else {
                    data.length = null;
                }
            }).catch((errorMsg) => {
                window.alert('Can\'t get authenticators list error: ' + errorMsg);
            });
        }

        authChanged(auth:Authenticator) : void {
            debug(auth);
            if (auth.isCustom)
                
                this.selected = auth;
        }

        doLogin() : void {
            debug('Login in');
        }
    }
    udsClientApp.controller("LoginController", LoginController)
}
