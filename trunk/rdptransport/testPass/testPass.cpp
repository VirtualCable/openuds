// testPass.cpp: define el punto de entrada de la aplicación de consola.
//

#include "stdafx.h"
#include <stdio.h>
#include <windows.h>
#include <Wincrypt.h>

void MyHandleError(char *s);

char arr[] = { '0', '1','2','3','4','5','6','7','8','9','A','B','C','D','E','F' };

void byteToHex(BYTE data)
{
	int n1 = data & 0x0f;
	int n2 = (data>>4) & 0x0f;
	printf("%c%c", arr[n2], arr[n1]);

}

void bytesToHex(BYTE* data, size_t len)
{
	for( int i = 0; i < len; i++ )
		byteToHex(data[i]);
	printf("\n");
}

int _tmain(int argc, _TCHAR* argv[])
{
	wchar_t* pass = L"temporal";
	printf("Size of wchar_t: %d\n", sizeof(wchar_t));
	DATA_BLOB DataIn;
	DATA_BLOB DataOut;
	DATA_BLOB DataVerify;
	BYTE *pbDataInput =(BYTE *)pass;
	DWORD cbDataInput = 16;//strlen((char *)pbDataInput)+1;
	DataIn.pbData = pbDataInput;
	DataIn.cbData = cbDataInput;
	//-------------------------------------------------------------------
	//  Begin processing.

	printf("The data to be encrypted is: %s\n",pass);

	//-------------------------------------------------------------------
	//  Begin protect phase.

	if(CryptProtectData(
		 &DataIn,
		 L"psw", // A description string. 
		 NULL,                               // Optional entropy
											 // not used.
		 NULL,                               // Reserved.
		 NULL,                      // Pass a PromptStruct.
		 CRYPTPROTECT_UI_FORBIDDEN,
		 &DataOut))
	{
		 printf("The encryption phase worked. \n");
		 printf("Data len: %d\n", DataOut.cbData);
		 printf("01000000D08C9DDF0115D1118C7A00C04FC297EB01000000FE75A256A68D3C4C881421C753628A9800000000080000007000730077000000106600000001000020000000D2A595F857AC73031C75AA190BCEF52327E7FE2B51A35D6C6AC03703DE115714000000000E8000000002000020000000F1C8AC290D19EFE11EEAA10B6A9F933105ADC8C04526A139000E7F535F2FCF6E20000000104E256EF4ABD26A8A7F506938E2A23127D7F9EB1CFFEEB6356445043F1E02C140000000ACC013C6D269C09DEB9B951E952348C12A5259C7A475AF66ED3861D9F8D1D1057449761332A4B624905CD043FEEB45918E0AE26245801E5ED229C43DF7872876\n");
		 bytesToHex(DataOut.pbData, DataOut.cbData);
	}
	else
	{
		MyHandleError("Encryption error!");
	}
	//-------------------------------------------------------------------
	//   Begin unprotect phase.

	if (CryptUnprotectData(
			&DataOut,
			NULL,
			NULL,                 // Optional entropy
			NULL,                 // Reserved
			NULL,        // Optional PromptStruct
			CRYPTPROTECT_UI_FORBIDDEN,
			&DataVerify))
	{
		 printf("The decrypted data is: %s\n", DataVerify.pbData);
	}
	else
	{
		MyHandleError("Decryption error!");
	}
	//-------------------------------------------------------------------
	// At this point, memcmp could be used to compare DataIn.pbData and 
	// DataVerify.pbDate for equality. If the two functions worked
	// correctly, the two byte strings are identical. 

	//-------------------------------------------------------------------
	//  Clean up.

	LocalFree(DataOut.pbData);
	LocalFree(DataVerify.pbData);
	char c;
	scanf("%c", &c);
} // End of main

//-------------------------------------------------------------------
//  This example uses the function MyHandleError, a simple error
//  handling function, to print an error message to the  
//  standard error (stderr) file and exit the program. 
//  For most applications, replace this function with one 
//  that does more extensive error reporting.

void MyHandleError(char *s)
{
    fprintf(stderr,"An error occurred in running the program. \n");
    fprintf(stderr,"%s\n",s);
    fprintf(stderr, "Error number %x.\n", GetLastError());
    fprintf(stderr, "Program terminating. \n");
    exit(1);
} // End of MyHandleError



