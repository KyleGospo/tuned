#!/usr/bin/env python3
import sys
import os
import dbus
import tuned.exports as exports
import tuned.consts as consts
from dbus.mainloop.glib import DBusGMainLoop
from tuned.ppd import controller


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Superuser permissions are required to run the daemon.", file=sys.stderr)
        sys.exit(1)

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    tuned_object = bus.get_object(consts.DBUS_BUS, consts.DBUS_OBJECT)
    tuned_iface = dbus.Interface(tuned_object, consts.DBUS_INTERFACE)

    controller = controller.Controller(bus, tuned_iface)
    dbus_exporter = exports.dbus.DBusExporter(
        consts.PPD_DBUS_BUS, consts.PPD_DBUS_INTERFACE, consts.PPD_DBUS_OBJECT
    )

    exports.register_exporter(dbus_exporter)
    exports.register_object(controller)
    exports.start()
