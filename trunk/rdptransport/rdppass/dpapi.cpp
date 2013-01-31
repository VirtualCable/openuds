#include "stdafx.h"
#include <jni.h>
#include <stdio.h>
#include <windows.h>
#include <wincrypt.h>
#include "net_sourceforge_jdpapi_DPAPI.h"

void throwByName(JNIEnv *env, const char *name, const char *msg) {
     jclass cls = env->FindClass(name);
     /* if cls is NULL, an exception has already been thrown */
     if (cls != NULL) {
         env->ThrowNew(cls, msg);
     }
     /* free the local ref */
     env->DeleteLocalRef(cls);
 }

void throwLastError(JNIEnv *env) {
    DWORD errorCode = GetLastError();
    LPVOID buf;

    int messageFlags = FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS;

    FormatMessage(messageFlags, NULL, errorCode, MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT), (LPTSTR) &buf, 0, NULL);
    
    throwByName(env, "net/sourceforge/jdpapi/DPAPIException", (char *) buf);
    LocalFree(buf);
 }

DWORD getFlags(jboolean useLocalMachine) {
    DWORD flags = CRYPTPROTECT_UI_FORBIDDEN;
    if (useLocalMachine) {
        flags |= CRYPTPROTECT_LOCAL_MACHINE;
    }
    return flags;
}

DATA_BLOB getBlobFromBytes(JNIEnv *env, jbyteArray bytes) {
    DATA_BLOB result;
    
    if (bytes != NULL) {
        result.pbData = (BYTE *) env->GetByteArrayElements(bytes, JNI_FALSE);
        result.cbData = (DWORD) env->GetArrayLength(bytes);
    } else {
        result.pbData = NULL;
        result.cbData = 0;
    }
    return result;
}

void freeBytesFromBlob(JNIEnv *env, jbyteArray originalBytes, DATA_BLOB blob) {
    if (originalBytes != NULL) {
        env->ReleaseByteArrayElements(originalBytes, (jbyte*) blob.pbData, JNI_ABORT);
    }
}

jstring getJStringFromBlob(JNIEnv *env, DATA_BLOB blob) {
    char * str = new char[blob.cbData + 1];
    memcpy(str, blob.pbData, blob.cbData);
    str[blob.cbData] = NULL;

    jstring result = env->NewStringUTF(str);

    delete str;
    LocalFree(blob.pbData);
    
    return result;
}

jbyteArray getJByteArrayFromBlob(JNIEnv *env, DATA_BLOB blob) {
	jbyteArray result = env->NewByteArray(blob.cbData);
    env->SetByteArrayRegion(result, 0, blob.cbData, (jbyte *)blob.pbData);

    LocalFree(blob.pbData);
    return result;
}

DATA_BLOB getBlobFromJString(JNIEnv *env, jstring str) {
    DATA_BLOB result;
    
    const jchar *nativeString = env->GetStringChars(str, 0);
	jsize len = env->GetStringLength(str);
    result.pbData = (BYTE *) nativeString;
    result.cbData = (DWORD)len*sizeof(wchar_t);
    
    return result;
}

void freeJStringFromBlob(JNIEnv *env, jstring original, DATA_BLOB blob) {
    env->ReleaseStringChars(original, (const jchar *) blob.pbData);
}

JNIEXPORT jbyteArray JNICALL Java_net_sourceforge_jdpapi_DPAPI_CryptProtectData
  (JNIEnv *env, jclass clazz, jstring key, jbyteArray entropyBytes, jboolean useLocalMachine) {
    
    DATA_BLOB output;   
    DATA_BLOB input = getBlobFromJString(env, key);
    DATA_BLOB entropy = getBlobFromBytes(env, entropyBytes);
    
//    BOOL completed = CryptProtectData(&input, L"psw", &entropy, NULL, NULL, getFlags(useLocalMachine), &output);
    BOOL completed = CryptProtectData(&input, L"psw", NULL, NULL, NULL, CRYPTPROTECT_UI_FORBIDDEN, &output);
    
    freeBytesFromBlob(env, entropyBytes, entropy);
    freeJStringFromBlob(env, key, input);
    
    if (!completed) {
        throwLastError(env);
        return NULL;
    }

    return getJByteArrayFromBlob(env, output);
}


JNIEXPORT jstring JNICALL Java_net_sourceforge_jdpapi_DPAPI_CryptUnprotectData
  (JNIEnv *env, jclass clazz, jbyteArray data, jbyteArray entropyBytes) {
    
    DATA_BLOB output;
    DATA_BLOB input = getBlobFromBytes(env, data);
    DATA_BLOB entropy = getBlobFromBytes(env, entropyBytes);
    
    BOOL completed = CryptUnprotectData(&input, (LPWSTR *) NULL, &entropy, NULL, NULL, getFlags(JNI_FALSE), &output);
    
    freeBytesFromBlob(env, entropyBytes, entropy);
    freeBytesFromBlob(env, data, input);
    
    if (!completed) {
        throwLastError(env);
        return NULL;
    }
    
    return getJStringFromBlob(env, output);
}