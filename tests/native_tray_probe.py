"""Run with dbus-run-session; simulates a tray host, never changes hardware."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import time
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from PySide6.QtWidgets import QApplication
from app import BatteryWindow

app=QApplication([])
app.setQuitOnLastWindowClosed(False)
bus=dbus.SessionBus(private=True, mainloop=DBusGMainLoop())
bus.request_name('org.kde.StatusNotifierWatcher')
registered=[]
class Watcher(dbus.service.Object):
    @dbus.service.method('org.kde.StatusNotifierWatcher', in_signature='s',out_signature='')
    def RegisterStatusNotifierItem(self,name):
        registered.append(str(name))
watcher=Watcher(bus,'/StatusNotifierWatcher')
w=BatteryWindow(demo=True)
assert w.tray.native is not None

def pump_until(predicate):
    deadline=time.monotonic()+3
    while not predicate() and time.monotonic()<deadline:
        app.processEvents()
        context=GLib.MainContext.default()
        while context.pending(): context.iteration(False)
        time.sleep(.005)
    assert predicate(), 'Timed out waiting for DBus reply'

pump_until(lambda: bool(registered))
proxy=bus.get_object(registered[0],'/StatusNotifierItem',introspect=False)
menu=bus.get_object(registered[0],'/Menu',introspect=False)

def call(proxy,method,*args,interface):
    replies=[]; errors=[]
    proxy.get_dbus_method(method,interface)(*args,reply_handler=lambda *v: replies.append(v),error_handler=errors.append)
    pump_until(lambda: bool(replies or errors))
    assert not errors, errors
    return replies[0]

for visible in (True,False,False):
    w.show() if visible else w.hide()
    app.processEvents()
    props=call(proxy,'GetAll','org.kde.StatusNotifierItem',interface='org.freedesktop.DBus.Properties')[0]
    assert props['ItemIsMenu'] and str(props['Menu'])=='/Menu'
    rev, layout=call(menu,'GetLayout',0,-1,dbus.Array([],signature='s'),interface='com.canonical.dbusmenu')
    labels=[str(child[1].get('label','')) for child in layout[2]]
    assert '打开主页面' in labels, labels
    assert not w.isVisible() if not visible else w.isVisible()
# The same exported actions update when the interface language changes.
import i18n
i18n.set_language('en', persist=False)
i18n.retranslate(w)
_, translated=call(menu,'GetLayout',0,-1,dbus.Array([],signature='s'),interface='com.canonical.dbusmenu')
assert any(child[1].get('label')=='Open main window' for child in translated[2])
i18n.set_language('zh', persist=False)
i18n.retranslate(w)
# Clicking the host-rendered action opens the hidden window.
ident=next(int(child[0]) for child in layout[2] if child[1].get('label')=='打开主页面')
call(menu,'Event',ident,'clicked',dbus.Int32(0),dbus.UInt32(0),interface='com.canonical.dbusmenu')
pump_until(w.isVisible)
w.tray.hide()
w.timer.stop()
bus.close()
print('PASS: native menu exported while shown/hidden; ItemIsMenu=true; menu action reopens window.')
