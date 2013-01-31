lib_LTLIBRARIES = libnss_uds.la
libnss_uds_la_SOURCES = shadow.c passwd.c group.c http.c http.h
libnss_uds_la_LDFLAGS = $(AM_LDFLAGS) -shrext .so.2
libnss_uds_la_LIBADD = $(CURL_LIBS) 

pam_http_PROGRAMS = pam_uds.so test
pam_httpdir = /lib/security

pam_uds_so_SOURCES=pam_uds.c http.c http.h
pam_uds_so_CFLAGS = -fPIC
pam_uds_so_LDFLAGS = -Xcompiler -shared $(CURL_LDFLAGS)
pam_uds_so_LDADD = $(CURL_LIBS) $(PAM_LIBS)


test_SOURCES = test.c http.c http.h
test_LDADD = $(CURL_LIBS)
test_CFLAGS = $(AM_CFLAGS)