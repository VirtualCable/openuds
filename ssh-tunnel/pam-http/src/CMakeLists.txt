# Very simple setup file
# We suppose that we already have pam develompent files & curl development files installed
set(pam_uds_SRCS
  pam_uds.c
  http.c
  http.h
)

set(nss_uds_SRCS
  shadow.c
  passwd.c
  group.c
  http.c
  http.h
)

add_library(pam_uds SHARED ${pam_uds_SRCS})
set_target_properties(pam_uds PROPERTIES
  OUTPUT_NAME pam_uds
  PREFIX ""
  SUFFIX ".so"
)
target_link_libraries(pam_uds curl pam)


add_library(nss_uds SHARED ${nss_uds_SRCS})

set_target_properties(nss_uds PROPERTIES
  OUTPUT_NAME nss_uds
  PREFIX "lib"
)
# Remember, nss libs needs to have ".so.2" symlink to .so

target_link_libraries(nss_uds curl)
