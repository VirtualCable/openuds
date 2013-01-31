/* (c) 2007 Adolfo Gómez */

#include <features.h>
#include <syslog.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>

#include "http.h"

#define PAM_SM_AUTH
#include <security/pam_modules.h>
#include <security/_pam_macros.h>

#define UDS_DEBUG      020	/* keep quiet about things */
#define UDS_QUIET      040	/* keep quiet about things */

/* some syslogging */
static void _log_err(int err, const char *format, ...)
{
	va_list args;

	va_start(args, format);
	openlog("PAM-uds", LOG_CONS|LOG_PID, LOG_AUTH);
	vsyslog(err, format, args);
	va_end(args);
	closelog();
}

static char baseUrl[128] = "";

static int _pam_parse(int flags, int argc, const char **argv)
{
	int ctrl = 0;

	/* does the appliction require quiet? */
	if ((flags & PAM_SILENT) == PAM_SILENT)
		ctrl |= UDS_QUIET;

	/* step through arguments */
	for (; argc-- > 0; ++argv)
	{
		if (!strcmp(*argv, "silent")) {
			ctrl |= UDS_QUIET;
		} else if (!strncmp(*argv,"base=",5)) {
			strncpy(baseUrl,*argv+5,sizeof(baseUrl));
			baseUrl[sizeof(baseUrl)-1] = '\0';
			_log_err(LOG_ERR, "option base: %s", baseUrl);
		} else {
			_log_err(LOG_ERR, "unknown option; %s", *argv);
		}
	}

	D(("ctrl = %o", ctrl));
	return ctrl;
}

/********************
 * PAM
 ********************/


PAM_EXTERN int pam_sm_authenticate(pam_handle_t *pamh, int flags, 
		int argc, const char **argv)
{
	const char *username;
	const char* passwd;
	int res;

	int rv = PAM_SUCCESS, ctrl;

	ctrl = _pam_parse(flags, argc, argv);

	if (strlen(baseUrl) == 0)
	{
		_log_err(LOG_ERR, "Need a host for authentication" );
		return PAM_AUTH_ERR;
	}

	if (pam_get_user(pamh, &username, 0) != PAM_SUCCESS) {
		_log_err( LOG_ERR, "Couldn't get username");
		return PAM_AUTH_ERR;
	}

	if( pam_get_item(pamh, PAM_AUTHTOK, (const void **)&passwd) != PAM_SUCCESS ) {
		_log_err( LOG_ERR, "Couldn't get password" );
		return PAM_AUTH_ERR;
	}

	if ( (res = httpAuthenticate(username, passwd, baseUrl)) != 0 ) {
		_log_err( LOG_ERR, "Failed to check credentials., base = %s, Result = %d", baseUrl, res );
		rv = PAM_AUTH_ERR;
	}
	else {
		rv = PAM_SUCCESS;
	}

	return rv;
}

PAM_EXTERN int pam_sm_setcred(pam_handle_t *pamh, int flags, 
		int argc, const char **argv)
{
	return PAM_SUCCESS;
}

