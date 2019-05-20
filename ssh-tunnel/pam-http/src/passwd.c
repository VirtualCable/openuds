#define _GNU_SOURCE 1

#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <nss.h>
#include <pwd.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>
#include <errno.h>
#include <ctype.h>
#include <fcntl.h>

#include <syslog.h>

#include "http.h"

char baseUrl[256] = { '\0' };

enum nss_status _nss_uds_getpwuid_r(uid_t,struct passwd *,char *, size_t,int *);
enum nss_status _nss_uds_setpwent (void);
enum nss_status _nss_uds_endpwent (void);
enum nss_status _nss_uds_getpwnam_r(const char *,struct passwd *,char *,size_t,int *);
enum nss_status _nss_uds_getpwent_r(struct passwd *, char *, size_t,int *);

static enum nss_status p_search(FILE *f,const char *name,const uid_t uid,struct passwd *pw, int *errnop,char *buffer, size_t buflen);


static void read_config(char* host, size_t size) {
  int n;
  FILE* f = fopen("/etc/uds.conf", "r");
  if( f != NULL ) {
    fgets( host, size-1, f );
    n = strlen(host) - 1;
    if( host[n] == '\n' )
      host[n] = '\0';
    fclose(f);
  } else {
    host[0] = '\0';
  }

}

enum nss_status _nss_uds_getpwuid_r(
  uid_t uid,
  struct passwd *result,
  char *buf,
  size_t buflen,
  int *errnop
) {
  char host[256];
  char *dir;
  read_config( host, sizeof(host) );

  if (result == NULL || buflen < 128 || *host == '\0')
    return NSS_STATUS_UNAVAIL;

  *errnop = getName( host, uid, buf, &result->pw_uid );

  if( *errnop != 0 )
    return NSS_STATUS_NOTFOUND;

  dir = buf + strlen(buf) + 1;
  sprintf( dir, "/var/udstmp", buf );
  result->pw_name = buf;
  result->pw_passwd = "*"; // This is really not used in our environment :)
  result->pw_gid = 65534; // Nogroup
  result->pw_gecos = "bugoma";
  result->pw_dir = dir;
  result->pw_shell = "/bin/false";
  return NSS_STATUS_SUCCESS;
}

enum nss_status _nss_uds_getpwnam_r(const char *name, struct passwd *result,
		char *buf, size_t buflen, int *errnop) {
  char host[256];
  char *dir;
  read_config( host, sizeof(host) );
  
  if (result == NULL || buflen < 128 || *host == '\0')
    return NSS_STATUS_UNAVAIL;

  *errnop = getUID( host, name, buf, &result->pw_uid );

  if( *errnop != 0 )
    return NSS_STATUS_NOTFOUND;

  dir = buf + strlen(buf) + 1;
  strcpy( dir, "/var/udstmp");
  result->pw_name = buf;
  result->pw_passwd = "*"; // This is really not used in our environment :)
  result->pw_gid = 65534; // Nogroup
  result->pw_gecos = "bugoma";
  result->pw_dir = dir;
  result->pw_shell = "/bin/false";
  return NSS_STATUS_SUCCESS;
}

enum nss_status _nss_uds_setpwent (void) {
         
  return NSS_STATUS_SUCCESS;
}

enum nss_status _nss_uds_endpwent (void) {
	return NSS_STATUS_SUCCESS;
}

enum nss_status _nss_uds_getpwent_r (struct passwd *pw,
                char * buffer, size_t buflen,int * errnop) {
    return NSS_STATUS_UNAVAIL;
}

