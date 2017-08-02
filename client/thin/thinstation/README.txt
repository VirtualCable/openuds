Steps:
1.- If building from repository, full copy (recursive) the "src" folder of "udsclient/thin" inside the "udsclient" folder. If building from the .tar.gz, simply ignor4e this step
2.- Copy the folder "udsclient" to /build/packages inside the thinstation build environment
3.- enter the chroot of thinstation
4.- go to the udsclient folder (/build/packages/udsclient)
5.- Execute "build.sh"
6.- Edit the file /build/build.conf, and add this line:
    package udsclient
7.- Execute the build process

Ready!!!
