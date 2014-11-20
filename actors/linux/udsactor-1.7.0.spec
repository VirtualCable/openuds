%define _topdir %(echo $PWD)/rpm
%define name udsactor
%define version 1.7.0
%define release 1
%define buildroot %{_topdir}/%{name}-%{version}-%{release}-root

BuildRoot: %{buildroot} 
Name: %{name}
Version: %{version}
Release: %{release}
Summary: Actor for Universal Desktop Services (UDS) Broker
License: BSD3
Group: Admin
Requires: python-six python-requests PyQt4

%define _rpmdir ../
%define _rpmfilename %%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm


%install
curdir=`pwd`
cd ../..
make DESTDIR=$RPM_BUILD_ROOT DISTRO=rh install
cd $curdir

%clean
rm -rf $RPM_BUILD_ROOT
curdir=`pwd`
cd ../..
make DESTDIR=$RPM_BUILD_ROOT DISTRO=rh clean
cd $curdir


%post
#!/bin/sh

%preun
#!/bin/sh

%postun
#!/bin/sh

%description
This package provides the required components to allow this machine to work on an environment managed by UDS Broker.

%files
%defattr(-,root,root)
/etc/udsactor
/etc/xdg/autostart/UDSActorTool.desktop
/etc/init.d/udsactor
/usr/bin/UDSActorTool-startup
/usr/bin/udsactor
/usr/bin/UDSActorTool
/usr/sbin/UDSActorConfig
/usr/sbin/UDSActorConfig-pkexec
/usr/share/UDSActor/*
/usr/share/applications/UDS_Actor_Configuration.desktop
/usr/share/autostart/UDSActorTool.desktop
/usr/share/polkit-1/actions/org.openuds.pkexec.UDSActorConfig.policy
