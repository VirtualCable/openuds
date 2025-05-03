OpenUDS
=======

OpenUDS (Universal Desktop Services) is a multiplatform connection broker for:
- VDI: Windows and Linux virtual desktops administration and deployment
- App virtualization
- Desktop services consolidation
- ...

This is an Open Source project, initiated by Spanish Company ​Virtual Cable and released Open Source with the help of several Spanish Universities.

Please feel free to contribute to this project.

Notes
=====
* Master version is always under heavy development and it is not recommended for use, it will probably have unfixed bugs.  Please use the latest stable branch. (v4.0 right now)
* From v4.0 onwards (current master), OpenUDS has been splitted in several repositories and contains submodules. Remember to use "git clone --resursive ..." to fetch it ;-).
* v3.6 version is tested on Python 3.9, 3.10 and 3.11. It will probably work on 3.8 too.
* v4.0 version will need Python 3.11 or higher. It uses new features only available on 3.10 or later, and is tested against 3.11. It will probably work on 3.10 too.
* We use "NamedTuples" in the code, and seems to be some kind of error on 3.11.1, so please do not use that python version: (Ref: https://github.com/python/cpython/issues/100098). 
