udsClientApp = angular.module('udsClientApp', []);

udsClientApp.controller('LoginController', ($scope) ->
    $scope.authenticators = [
        {
            'id': 1,
            'name': 'Authenticator'
        },
        {
            'id': 2,
            'name': 'second Authenticator'
        },
        {
            'id': 3,
            'name': 'third Authenticator'
        },
        {
            'id': 4,
            'name': 'fourth Authenticator'
        },
    ]
    return
)