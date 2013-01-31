#ifndef __HTTP_H_DK__
#define __HTTP_H_DK__


int httpAuthenticate(const char* username, const char* password, const char* authHost);

int getUID( const char* host, const char* name, char* username, int* uid );


int getName( const char* host, int id, char* username, int* uid );


#endif
