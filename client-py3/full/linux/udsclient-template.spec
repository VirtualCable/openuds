%define _topdir %(echo $PWD)/rpm
%define name udsclient
%define version 0.0.0
%define release 1
%define buildroot %{_topdir}/%{name}-%{version}-%{release}-root

BuildRoot: %{buildroot} 
Name: %{name}
Version: %{version}
Release: %{release}
Summary: Client for Universal Desktop Services (UDS) Broker
License: BSD3
Group: Applications/Productivity
Requires: python-six python-paramiko PyQt4
Vendor: Virtual Cable S.L.U.
URL: http://www.udsenterprise.com
Provides: udsclient

%define _rpmdir ../
%define _rpmfilename %%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm


%install
curdir=`pwd`
cd ../..
make DESTDIR=$RPM_BUILD_ROOT DISTRO=rh install
cd $curdir

%post
/usr/bin/update-desktop-database

%clean
rm -rf $RPM_BUILD_ROOT
curdir=`pwd`
cd ../..
make DESTDIR=$RPM_BUILD_ROOT DISTRO=rh clean
cd $curdir


%postun
# And, posibly, the .pyc leaved behind on /usr/share/UDSActor
rm -rf /usr/share/UDClient > /dev/null 2>&1
/usr/bin/update-desktop-database

%description
This package provides the required components to allow connection to services offered by UDS Broker.

%files
%defattr(-,root,root)
/usr/lib/UDSClient/*
/usr/share/applications/UDSClient.desktop
