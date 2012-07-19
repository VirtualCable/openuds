/*
 * test.c
 *
 *  Created on: Jan 4, 2012
 *      Author: dkmaster
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "http.h"

int main(int argc, char** argv)
{
	int id;
	char username[128];
	const char* baseUrl = "http://172.27.0.1:8000/pam";


	printf("Authenticate: %d\n", httpAuthenticate("pepito", "juanito", baseUrl));

	int res = getUID(baseUrl,"pepito", username, &id);
	printf("GetUID:res: %d, username: %s, id: %d\n", res, username, id);

	*username = '\0';
	res = getName(baseUrl, 10000, username, &id);
	printf("GetName:res: %d, username: %s, id: %d\n", res, username, id);

}
