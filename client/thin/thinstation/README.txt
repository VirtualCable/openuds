Steps:
1.- If building from repository, full copy (recursive) the "src" folder of "client/thin" (from openuds project) inside the "udsclient" folder here (so we will have an client/thin/udsclient/src folder, with the source code of thin client). If building from the .tar.gz, simply ignore this step
2.- Copy the folder "udsclient" to /build/packages inside the thinstation build environment
3.- enter the chroot of thinstation
4.- go to the udsclient folder (/build/packages/udsclient)
5.- Execute "build.sh"
6.- Edit the file /build/build.conf, and add this line:
    package udsclient
7.- Execute the build process

Ready!!!
