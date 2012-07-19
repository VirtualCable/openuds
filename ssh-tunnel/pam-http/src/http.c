#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <curl/curl.h>
#include <curl/easy.h>

#define DATASIZE 256
#define UID "uid"
#define NAME "name"
#define AUTHID "id"
#define AUTHPASS "pass"

struct OutputData {
  char*    buffer;
  size_t   size;
  size_t   pos;
 };
 

static size_t authenticatorData(void *buffer, size_t size, size_t nmemb, void *userp) {
  struct OutputData* data = (struct OutputData*)userp;
  size_t realSize = size * nmemb;
  if( data->pos + realSize >= data->size )
    return 0;
  memcpy( data->buffer + data->pos, buffer, realSize );
  data->pos += realSize;
  return realSize;
}
 
static int getUrl(const char* url, char* buffer, size_t size ) {
  CURL *curl = curl_easy_init();
  CURLcode res = -1;
  
  struct OutputData* data = malloc(sizeof(struct OutputData));
  data->buffer = buffer;
  data->size = size;
  data->pos = 0;
  
  if (!curl) return -1;
  
  curl_easy_setopt(curl, CURLOPT_URL, url);
  curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, authenticatorData);
  curl_easy_setopt(curl, CURLOPT_WRITEDATA, data );
  /* provide no progress indicator */
  curl_easy_setopt(curl, CURLOPT_NOPROGRESS, 1);
  /* fail on HTTP errors */
  curl_easy_setopt(curl, CURLOPT_FAILONERROR, 1);
  
  curl_easy_setopt(curl, CURLOPT_RANDOM_FILE, "/dev/urandom");
  curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0); 
  curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0 );
  
  res = curl_easy_perform(curl);
 
 cleanup:
  curl_easy_cleanup(curl);
  buffer[data->pos] = '\0';
  free(data);

  return res;
  
}
 
int httpAuthenticate(const char* username, const char* password, const char* authHost)
{
  char* buffer = malloc(DATASIZE);
  char* url = malloc(256);
  int res;
  
  sprintf( url, "%s?%s=%s&%s=%s", authHost, AUTHID, username, AUTHPASS, password );
  res = getUrl( url, buffer, DATASIZE );
  free(url);
  
  if( res == 0 && buffer[0] == '0' )
    res = -1;
  

  free(buffer);
  
  return res;
}

static int getUserData( const char* host, const char* kind, const char* id, char* username, int* uid ) {
  char* buffer = malloc(DATASIZE);
  char* url = malloc(256);
  int res;
  
  *username = '\0';
  *uid = -1;
  
  sprintf( url, "%s?%s=%s", host, kind, id );
  res = getUrl( url, buffer, DATASIZE );
  free(url);
  
  if( res == 0 ) {
	  if( *buffer == '*' )
		  res = -1;
	  else {
		  sscanf( buffer, "%d %s", uid, username );
		  if( *uid == -1 )
		    res = -1;
	 }

  }

  free(buffer);
  
  return res;
}

int getUID( const char* host, const char* name, char* username, int* uid ) {
  return getUserData( host, UID, name, username, uid );
}

int getName( const char* host, int id, char* username, int* uid ) {
  char tmp[32];
  sprintf( tmp, "%d", id );
  return getUserData( host, NAME, tmp, username, uid );
}
