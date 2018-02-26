/// <reference path="params.ts" />

namespace uds {

    // Authenticator 
    export interface Authenticator {
        auth: string;
        authId: string;
        priority: number;
        isCustom: boolean;
    }

    export class API {
        private authData : string;

        constructor(
            private $http:ng.IHttpService,
            private $q: ng.IQService
        ) {
        }

        // Get info about available authenticators
        getAuthenticators() : angular.IPromise<Authenticator[]> {
            let deferred : angular.IDeferred<Authenticator[]> = this.$q.defer();
            this.$http.get('rest/auth/auths?all=true')
                .then((response:angular.IHttpResponse<Authenticator[]>) => {
                    let data = response.data.sort((a,b) => a.priority - b.priority);
                    console.log(data);
                    deferred.resolve(data);
                }, (errorMsg) => {
                    deferred.reject(errorMsg);
                } );

            return deferred.promise;

        }
    }
}
