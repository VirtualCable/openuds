dnl Process this file with autoconf to produce a configure script.

AC_PREREQ(2.59)
AC_INIT(pam-http, 1.0)


AC_CANONICAL_SYSTEM
AC_CONFIG_MACRO_DIR([m4])

AM_INIT_AUTOMAKE(pam-http, 1.0)


AC_PROG_CC
AC_PROG_LIBTOOL
AM_PROG_CC_C_O

AC_CHECK_LIB(pam, pam_get_user, ,AC_MSG_ERROR([PAM library missing]))
AC_CHECK_LIB([pam], [main],,AC_MSG_ERROR(libpam-devel >1.0 Not Found))
AC_CHECK_HEADER([security/pam_modules.h], ,[AC_MSG_ERROR([PAM headers missing])])

PKG_CHECK_MODULES(CURL, [libcurl >= 7.0.0])


AC_CONFIG_FILES(Makefile src/Makefile)
AC_OUTPUT

