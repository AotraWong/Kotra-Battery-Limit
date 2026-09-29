Name:           kotra-battery-limit
Version:        0.1~beta1
Release:        1%{?dist}
Summary:        Battery charge limit utility for Asahi Linux

License:        GPL-3.0-only
URL:            https://github.com/AotraWong/Kotra-Battery-Limit
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

Requires:       python3 >= 3.10
Requires:       python3-pyside6 >= 6.6
Requires:       python3-dbus
Requires:       python3-gobject
Requires:       polkit

%description
A Qt system tray application for viewing battery information
and controlling macsmc-battery charging thresholds on Asahi Linux.

%prep
%autosetup

%build
# Pure Python application; no compilation required.

%install
install -d %{buildroot}%{_datadir}/%{name}
install -m 0644 app.py about_dialog.py app_logging.py \
    battery_backend.py cli.py i18n.py native_tray.py \
    threshold_helper.py LICENSE \
    %{buildroot}%{_datadir}/%{name}/

install -d %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/kbl <<'EOF'
#!/bin/sh
exec /usr/bin/python3 /usr/share/kotra-battery-limit/app.py "$@"
EOF
chmod 0755 %{buildroot}%{_bindir}/kbl

install -d %{buildroot}%{_datadir}/applications
cat > %{buildroot}%{_datadir}/applications/%{name}.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Kotra Battery Limit
Comment=Battery charging thresholds for Asahi Linux
Comment[zh_CN]=Asahi 电池充电阈值管理
Exec=kbl
Icon=battery
Terminal=false
Categories=Settings;HardwareSettings;
EOF

%files
%license LICENSE
%doc README.md
%{_bindir}/kbl
%{_datadir}/%{name}/
%{_datadir}/applications/%{name}.desktop