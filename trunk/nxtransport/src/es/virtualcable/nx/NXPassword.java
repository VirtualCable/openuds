package es.virtualcable.nx;

import java.util.HashMap;

public class NXPassword {
	// Encoding method extracted from nomachine web site:
	// http://www.nomachine.com/ar/view.php?ar_id=AR01C00125
	
	private static final int numValidCharList = 85;
	private static final String dummyString = "{{{{";
	private static final char[] validCharList = {
		  '!',  '#',  '$',  '%',  '&',  '(', ')',  '*',  '+',  '-',
		  '.',  '0',   '1',  '2',   '3',  '4',  '5',  '6', '7', '8',
		  '9', ':',  ';',  '<',  '>',  '?',  '@',  'A',  'B', 'C',
		  'D',  'E',  'F',  'G',  'H',  'I',  'J',  'K',  'L', 'M',
		  'N', 'O',  'P',  'Q',  'R',  'S',  'T', 'U', 'V', 'W',
		  'X',  'Y',  'Z',  '[', ']',  '_',  'a',  'b',  'c',  'd',
		  'e',  'f',  'g',  'h',  'i',  'j',  'k',  'l',  'm',  'n',
		  'o',  'p',  'q',  'r',  's',  't',  'u',  'v',  'w',  'x',
		  'y',  'z',  '{',  '|',  '}'
		};		
	
	private static StringBuilder encodePassword(String p)
	{
	  StringBuilder sPass =  new StringBuilder(":");

	  if (p.length() == 0)
	    return new StringBuilder("");

	  for (int i = 0; i < p.length(); i++)
	  {
	    char c = (char)p.charAt(i);
	    sPass.append(c+i+1).append(":");
	  }

	  return sPass;
	}
	
	private static int findCharInList(char c)
	{
	  int i = -1;

	  for (int j = 0; j < numValidCharList; j++)
	  {
	    if (validCharList[j] == c)
	    {
	      i = j;
	      return i;
	    }
	  }

	  return i;
	}
	
	private static char getRandomValidCharFromList()
	{
	 // int k = (int)(java.lang.System.currentTimeMillis() % 60);
	  int k = 0;
	  return validCharList[k];
	}
	
	public static String scrambleString(String s)
	{
	  StringBuilder pass = new StringBuilder();

	  if (s == null || s.length() == 0)
	    return s;

	  StringBuilder str = encodePassword(s);

	  if (str.length() < 32)
	    str.append(dummyString);

	  pass.append(str.reverse()); 

	  if (pass.length() < 32)
	    pass.append(dummyString);

	  int k = getRandomValidCharFromList();
	  int l = k + pass.length() - 2;

	  pass.insert(0, (char)k);
	  
	  for (int i1 = 1; i1 < (int)pass.length(); i1++)
	  {
	    int j = findCharInList(pass.charAt(i1));

	    if (j == -1)
	      return s;

	    int i = (j + l * (i1 + 1)) % numValidCharList;

	    pass.setCharAt(i1,validCharList[i]);
	  }

	  char c = (char)(getRandomValidCharFromList() + 2);
	  pass.append(c);
	  
	  // Convert entities
	  HashMap<Character, String> replacements = new HashMap<Character, String>();
	  replacements.put('&', "&amp;");
	  replacements.put('<', "&lt;");
	  replacements.put('"', "&quot;");
	  replacements.put('\'', "&apos;");
	  // And convert $ to \$
	  replacements.put('$', "\\$");
	  
	  StringBuilder result = new StringBuilder();
	  for( int i = 0; i < pass.length(); i++ )
	  {
		  c = pass.charAt(i);
		  if( replacements.containsKey(c) )
			  result.append(replacements.get(c));
		  else
			  result.append(c);
	  }

	  return result.toString();
	}	
	
	
}
