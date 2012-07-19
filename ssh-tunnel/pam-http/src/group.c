#define _GNU_SOURCE 1

#include <stdio.h>
#include <stdlib.h>
#include <nss.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>
#include <errno.h>
#include <ctype.h>
#include <grp.h>


enum nss_status _nss_uds_setgrent (void);
enum nss_status _nss_uds_endgrent (void);
enum nss_status _nss_uds_getgrent_r (struct group *gr,
		char * buffer, size_t buflen,int * errnop);
enum nss_status _nss_uds_getgrnam_r (const char * name, struct group *gr,
		char * buffer, size_t buflen,int *errnop);
enum nss_status _nss_uds_getgrgid_r (const gid_t gid, struct group *gr,
		char * buffer, size_t buflen,int *errnop);


enum nss_status _nss_uds_setgrent (void) {
}

enum nss_status _nss_uds_endgrent (void) {
}


enum nss_status _nss_uds_getgrent_r (struct group *gr,
		char * buffer, size_t buflen,int * errnop) {
}


enum nss_status _nss_uds_getgrnam_r (const char * name, struct group *gr,
		char * buffer, size_t buflen,int *errnop) {
}

enum nss_status _nss_uds_getgrgid_r (const gid_t gid, struct group *gr,
		char * buffer, size_t buflen,int *errnop) {
}
