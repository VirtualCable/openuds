%define _topdir %(echo $PWD)/rpm
%define name udsactor
%define version 0.0.0
%define release 1
%define buildroot %{_topdir}/%{name}-%{version}-%{release}-root

BuildRoot: %{buildroot} 
Name: %{name}
Version: %{version}
Release: %{release}
Summary: Actor for Universal Desktop Services (UDS) Broker
License: BSD3
Group: Admin
Requires: python-six python-requests PyQt4 libXScrnSaver
Vendor: Virtual Cable S.L.U.
URL: http://www.udsenterprise.com
Provides: udsactor

%define _rpmdir ../
%define _rpmfilename %%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm


%install
curdir=`pwd`
cd ../..
make DESTDIR=$RPM_BUILD_ROOT DISTRO=rh install-udsactor
cd $curdir

%clean
rm -rf $RPM_BUILD_ROOT
curdir=`pwd`
cd ../..
make DESTDIR=$RPM_BUILD_ROOT DISTRO=rh clean
cd $curdir


%post
systemctl enable udsactor.service > /dev/null 2>&1

%preun
systemctl disable udsactor.service > /dev/null 2>&1
systemctl stop udsactor.service > /dev/null 2>&1

%postun
# $1 == 0 on uninstall, == 1 on upgrade for preun and postun (just a reminder for me... :) )
if [ $1 -eq 0 ]; then
    rm -rf /etc/udsactor
    rm /var/log/udsactor.log
fi
# And, posibly, the .pyc leaved behind on /usr/share/UDSActor
rm -rf /usr/share/UDSActor > /dev/null 2>&1

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
