set(uds_pam_SRCS
  pam_uds.c
  http.c
  http.h
)

add_library(uds_pam SHARED ${uds_pam_SRCS})
