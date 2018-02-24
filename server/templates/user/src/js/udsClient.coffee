udsClientApp = angular.module('udsClientApp', ['ngCookies']);

udsClientApp.controller('LoginController', ($scope, $http, $cookies) ->
    $scope.authenticators = []
    $scope.selected = null

    console.log $cookies.get('authToken')
    if $cookies.get('authToken') == undefined
        alert('No auth token')
        $cookies.put('authToken', '1234')

    # On change authenticator, reflect it and process if needed more actions
    $scope.authChanged = (auth) ->
        $scope.selected = auth
        if auth.isCustom
            alert('Custom Authenticator')
    $http
        .get('rest/auth/auths?all=true')
        .then((response) ->
            data = response.data.sort( (first, second) ->
                return first.priority > second.priority
            )
            console.log(data)
            $scope.authenticators = data
            $scope.selected = if data.length > 0 then data[0] else null
        )
    console.log($scope.authenticators)
    return
)