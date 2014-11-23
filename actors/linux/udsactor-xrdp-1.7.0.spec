%define _topdir %(echo $PWD)/rpm
%define name udsactor-xrdp
%define version 1.7.0
%define release 1
%define buildroot %{_topdir}/%{name}-%{version}-%{release}-root

BuildRoot: %{buildroot} 
Name: %{name}
Version: %{version}
Release: %{release}
Summary: Glue between UDS Actor and XRDP
License: BSD3
Group: Admin
Requires: xrdp udsactor pam
Vendor: Virtual Cable S.L.U.
URL: http://www.udsenterprise.com
Provides: udsactor-xrdp

%define _rpmdir ../
%define _rpmfilename %%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm


%install
curdir=`pwd`
cd ../..
make DESTDIR=$RPM_BUILD_ROOT DISTRO=rh install-udsactor-xrdp
cd $curdir

%clean
rm -rf $RPM_BUILD_ROOT
curdir=`pwd`
cd ../..
make DESTDIR=$RPM_BUILD_ROOT DISTRO=rh clean
cd $curdir


%post
SESMANFILE=/etc/pam.d/xrdp-sesman
TMPFILE=$(mktemp /tmp/sesman.XXXXX)
grep -v uds $SESMANFILE > $TMPFILE
echo >> $TMPFILE
echo "# Added by udsactor-xrdp" >> $TMPFILE
echo "session optional pam_exec.so /usr/bin/uds-sesman" >> $TMPFILE
cp $TMPFILE $SESMANFILE
rm $TMPFILE > /dev/null 2>&1

%preun

%postun
SESMANFILE=/etc/pam.d/xrdp-sesman
TMPFILE=$(mktemp /tmp/sesman.XXXXX)
grep -v uds $SESMANFILE > $TMPFILE
cp $TMPFILE $SESMANFILE
rm $TMPFILE > /dev/null 2>&1

%description
This package provides the required components to allow this machine to work on an environment managed by UDS Broker.

%files
%defattr(-,root,root)
/usr/bin/*