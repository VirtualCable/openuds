/// <reference path="_udsClientRestService.ts" />

namespace uds {
    var udsClientApp = angular.module('udsClientApp', ['ngCookies']);

    class LoginController {
        selected: any;
        authenticators: any;
        rest : REST;

        // Order is important!!, must mucht those on constructor
        // This tells angular the requred services, etc... to be passed to constructor
        static $inject = ["$http", "$cookies", "$q"];

        constructor(
            private $http: ng.IHttpService,
            private $cookies: ng.cookies.ICookiesService,
            private $q: ng.IQService
        ) {
            this.selected = null;
            this.authenticators = [];
            this.rest = new REST($http, $cookies, $q);

            this.rest.login("", "test", "test").then(() => {
                window.alert('Login Correct');
            }).catch((errorMsg) => {
                window.alert('Login error: ' + errorMsg);
            });

            this.rest.getAuthenticators().then((data) => {
                this.authenticators = data;
                this.selected = data[0];
            })
        }

        authChanged(auth:any) : void {
            console.log(auth);
            this.selected = auth;
        }
    }
udsClientApp.controller("LoginController", LoginController)
}
