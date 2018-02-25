namespace uds {
    let devel = true;

    // Authenticator 
    interface Authenticator {
        auth: string;
        authId: string;
        priority: number;
        isCustom: boolean;
    }

    // Login response
    interface LoginResponse {
        result: string;
        token: string;
        version: string;
        scrambler: string;
        }

    export class REST {
        private authData : string;

        constructor(
            private $http:ng.IHttpService,
            private $cookies: ng.cookies.ICookiesService,
            private $q: ng.IQService
        ) {
        }

        private postJson(url, data:any, addAuth=false) {
            if (addAuth) {
                // TODO: Add auth header
            }
            let toPost = JSON.stringify(data);
            console.log('topost: ' + toPost);
            if(devel) {
                return this.$http.get(url);
            } else {
                return this.$http.post(url, toPost);
            }
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

        // Tries to login with provided credentials
        login(authId:string, username: string, password: string) {
            let deferred = this.$q.defer();

            this.postJson('rest/auth/login',{ authId: authId, username: username, password: password } )
                .then((response:angular.IHttpResponse<LoginResponse>) => {
                    if(response.data.result == 'ok') {
                        deferred.resolve();
                    } else {
                        deferred.reject('Invalid credentials');
                    }

                    
                }, (errorMsg) => {
                    deferred.reject(errorMsg);
                })


            return deferred.promise;
        }

    }
}
