"""Menu-only StatusNotifierItem for Wayland: the desktop renders both clicks.

Uses dbus-python and GLib when available, with QSystemTrayIcon fallback.
No popup surface or visible application window is needed by the native host.
"""
import os
from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from app_logging import logger


class MenuTrayIcon(QSystemTrayIcon):
    def __init__(self, icon, parent=None):
        super().__init__(icon, parent)
        self.native = None
        self._native_icon = icon
        self._native_tooltip = ''
        self._native_menu = None
        self._native_attempted = False
        QApplication.instance().aboutToQuit.connect(self.hide)

    def setContextMenu(self, menu):
        self._native_menu = menu
        super().setContextMenu(menu)

    def show(self):
        if not self._native_attempted:
            self._native_attempted = True
            try:
                self.native = create_native(self)
                logger.info('Native menu-only tray enabled / 已启用桌面原生托盘菜单')
            except Exception as exc:
                logger.warning('Native tray unavailable; using Qt / 原生托盘不可用，使用 Qt: %s', exc)
        if self.native is None:
            super().show()

    def hide(self):
        if self.native is not None:
            self.native.close()
            self.native = None
            self._native_attempted = False
        super().hide()

    def setIcon(self, icon):
        self._native_icon = icon
        if self.native is not None:
            self.native.item.NewIcon()
        else:
            super().setIcon(icon)

    def setToolTip(self, text):
        self._native_tooltip = text
        if self.native is not None:
            self.native.item.NewToolTip()
        else:
            super().setToolTip(text)

    def toolTip(self):
        return self._native_tooltip


def create_native(tray):
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib

    bus = dbus.SessionBus(private=True, mainloop=DBusGMainLoop())
    watcher = 'org.kde.StatusNotifierWatcher'
    if not bus.name_has_owner(watcher):
        bus.close()
        raise RuntimeError('No StatusNotifierWatcher')
    name = f'org.kde.StatusNotifierItem-{os.getpid()}-{id(tray)}'
    item_interface = 'org.kde.StatusNotifierItem'
    menu_interface = 'com.canonical.dbusmenu'
    properties_interface = 'org.freedesktop.DBus.Properties'
    if bus.request_name(name, dbus.bus.NAME_FLAG_DO_NOT_QUEUE) != dbus.bus.REQUEST_NAME_REPLY_PRIMARY_OWNER:
        bus.close()
        raise RuntimeError('Could not acquire tray service name')

    class Properties(dbus.service.Object):
        @dbus.service.method(properties_interface, in_signature='ss', out_signature='v')
        def Get(self, interface, prop):
            return self.GetAll(interface)[prop]

        @dbus.service.method(properties_interface, in_signature='s', out_signature='a{sv}')
        def GetAll(self, interface):
            return self.properties() if interface == self.interface else {}

        @dbus.service.method(properties_interface, in_signature='ssv', out_signature='')
        def Set(self, interface, prop, value):
            raise dbus.exceptions.DBusException('Read-only property', name='org.freedesktop.DBus.Error.PropertyReadOnly')

    class Menu(Properties):
        interface = menu_interface
        revision = 1

        def __init__(self):
            super().__init__(bus, '/Menu')
            self.actions = {i: action for i, action in enumerate(tray._native_menu.actions(), 1)}
            for action in self.actions.values():
                action.changed.connect(self.changed)

        def properties(self):
            return {'Version': dbus.UInt32(3), 'TextDirection': 'ltr', 'Status': 'normal',
                    'IconThemePath': dbus.Array([], signature='s')}

        def action_properties(self, ident, names):
            if ident == 0:
                result = {'children-display': 'submenu'}
            else:
                action = self.actions[ident]
                result = {'label': action.text().replace('&&', '&'), 'enabled': action.isEnabled(), 'visible': action.isVisible()}
                if action.isSeparator():
                    result['type'] = 'separator'
            return dbus.Dictionary({k: v for k, v in result.items() if not names or k in names}, signature='sv')

        @dbus.service.method(menu_interface, in_signature='iias', out_signature='u(ia{sv}av)')
        def GetLayout(self, parent, depth, names):
            children = []
            if parent == 0 and depth != 0:
                children = [dbus.Struct((i, self.action_properties(i, names), dbus.Array([], signature='v')), signature='ia{sv}av', variant_level=1) for i in self.actions]
            return dbus.UInt32(self.revision), (parent, self.action_properties(parent, names), dbus.Array(children, signature='v'))

        @dbus.service.method(menu_interface, in_signature='aias', out_signature='a(ia{sv})')
        def GetGroupProperties(self, ids, names):
            return [(i, self.action_properties(i, names)) for i in ids if i == 0 or i in self.actions]

        @dbus.service.method(menu_interface, in_signature='is', out_signature='v')
        def GetProperty(self, ident, name):
            return self.action_properties(ident, [name])[name]

        @dbus.service.method(menu_interface, in_signature='isvu', out_signature='')
        def Event(self, ident, event, data, timestamp):
            action = self.actions.get(ident)
            if event == 'clicked' and action is not None and action.isEnabled() and action.isVisible():
                QTimer.singleShot(0, action.trigger)

        @dbus.service.method(menu_interface, in_signature='a(isvu)', out_signature='ai')
        def EventGroup(self, events):
            errors = []
            for ident, event, data, timestamp in events:
                if ident not in self.actions:
                    errors.append(ident)
                else:
                    self.Event(ident, event, data, timestamp)
            return errors

        @dbus.service.method(menu_interface, in_signature='i', out_signature='b')
        def AboutToShow(self, ident):
            return False

        @dbus.service.method(menu_interface, in_signature='ai', out_signature='aiai')
        def AboutToShowGroup(self, ids):
            return [], [i for i in ids if i != 0 and i not in self.actions]

        @dbus.service.signal(menu_interface, signature='ui')
        def LayoutUpdated(self, revision, parent):
            pass

        def changed(self):
            self.revision += 1
            self.LayoutUpdated(self.revision, 0)

    class Item(Properties):
        interface = item_interface

        def properties(self):
            image = tray._native_icon.pixmap(64, 64).toImage().convertToFormat(QImage.Format.Format_RGBA8888)
            rgba = bytes(image.constBits())
            argb = bytearray(len(rgba))
            argb[0::4], argb[1::4], argb[2::4], argb[3::4] = rgba[3::4], rgba[0::4], rgba[1::4], rgba[2::4]
            pixels = dbus.Array([(image.width(), image.height(), dbus.ByteArray(argb))], signature='(iiay)')
            return {'Category': 'ApplicationStatus', 'Id': 'kotra-battery-limit', 'Title': 'Kotra Battery Limit',
                    'Status': 'Active', 'WindowId': dbus.UInt32(0), 'IconName': '', 'IconPixmap': pixels,
                    'ItemIsMenu': True, 'Menu': dbus.ObjectPath('/Menu'),
                    'ToolTip': dbus.Struct(('', pixels, 'Kotra Battery Limit', tray.toolTip()), signature='sa(iiay)ss')}

        @dbus.service.method(item_interface, in_signature='ii', out_signature='')
        def Activate(self, x, y):
            # Compliant hosts use ItemIsMenu and render the exported menu.
            self.ContextMenu(x, y)

        @dbus.service.method(item_interface, in_signature='ii', out_signature='')
        def ContextMenu(self, x, y):
            pass

        @dbus.service.method(item_interface, in_signature='ii', out_signature='')
        def SecondaryActivate(self, x, y):
            pass

        @dbus.service.method(item_interface, in_signature='is', out_signature='')
        def Scroll(self, delta, orientation):
            pass

        @dbus.service.signal(item_interface, signature='')
        def NewIcon(self):
            pass

        @dbus.service.signal(item_interface, signature='')
        def NewToolTip(self):
            pass

    class Native:
        def __init__(self):
            self.menu = Menu()
            self.item = Item(bus, '/StatusNotifierItem')
            self.timer = QTimer(tray)
            self.timer.timeout.connect(self.dispatch)
            self.timer.start(50)
            self.watch = bus.add_signal_receiver(self.owner_changed, signal_name='NameOwnerChanged', dbus_interface='org.freedesktop.DBus', arg0=watcher)
            self.register()

        def register(self):
            bus.get_object(watcher, '/StatusNotifierWatcher', introspect=False).RegisterStatusNotifierItem(name, dbus_interface=watcher, reply_handler=lambda: None, error_handler=lambda exc: logger.warning('Tray registration failed / 托盘注册失败: %s', exc))

        def owner_changed(self, service, old, new):
            if new:
                self.register()

        def dispatch(self):
            context = GLib.MainContext.default()
            for _ in range(20):
                if not context.pending():
                    break
                context.iteration(False)

        def close(self):
            self.timer.stop()
            self.timer.deleteLater()
            self.watch.remove()
            for action in self.menu.actions.values():
                action.changed.disconnect(self.menu.changed)
            self.item.remove_from_connection()
            self.menu.remove_from_connection()
            bus.release_name(name)
            bus.close()

    try:
        return Native()
    except Exception:
        bus.close()
        raise
