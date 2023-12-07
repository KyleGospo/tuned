from tuned import exports, logs
from enum import StrEnum
import dbus

log = logs.get()

DRIVER = "TuneD"


class PPDProfile(StrEnum):
    POWER_SAVER = "power-saver"
    BALANCED = "balanced"
    PERFORMANCE = "performance"


class TuneDProfile(StrEnum):
    POWERSAVE = "powersave"
    BALANCED = "balanced"
    THROUGHPUT_PERFORMANCE = "throughput-performance"


PPD_TO_TUNED = {
    PPDProfile.POWER_SAVER: TuneDProfile.POWERSAVE,
    PPDProfile.BALANCED: TuneDProfile.BALANCED,
    PPDProfile.PERFORMANCE: TuneDProfile.THROUGHPUT_PERFORMANCE,
}

TUNED_TO_PPD = {
    TuneDProfile.POWERSAVE: PPDProfile.POWER_SAVER,
    TuneDProfile.BALANCED: PPDProfile.BALANCED,
    TuneDProfile.THROUGHPUT_PERFORMANCE: PPDProfile.PERFORMANCE,
}


class ProfileHold(object):
    def __init__(self, profile, reason, app_id, watch):
        self.profile = profile
        self.reason = reason
        self.app_id = app_id
        self.watch = watch

    def as_dict(self):
        return {
            "Profile": self.profile,
            "Reason": self.reason,
            "ApplicationId": self.app_id,
        }


class ProfileHoldManager(object):
    def __init__(self, controller):
        self._holds = {}
        self._cookie_counter = 0
        self._controller = controller

    @property
    def holds(self):
        return self._holds

    def _callback(self, cookie, app_id):
        def callback(name):
            if name == "":
                log.info(
                    f"Application '{app_id}' dissappeared, releasing hold '{cookie}'"
                )
                self.remove(cookie)

        return callback

    def _effective_hold_profile(self):
        if any(hold.profile == PPDProfile.POWER_SAVER for hold in self._holds.values()):
            return PPDProfile.POWER_SAVER
        return PPDProfile.PERFORMANCE

    def _cancel(self, cookie):
        if cookie not in self._holds:
            return
        hold = self._holds.pop(cookie)
        hold.watch.cancel()
        exports.send_signal("ProfileReleased", cookie)
        log.info(
            f"Releasing hold '{cookie}': profile '{hold.profile}' by application '{hold.app_id}'"
        )

    def add(self, profile, reason, app_id, caller):
        cookie = self._cookie_counter
        self._cookie_counter += 1
        watch = self._controller.bus.watch_name_owner(
            caller, self._callback(cookie, app_id)
        )
        log.info(
            f"Adding hold '{cookie}': profile '{profile}' by application '{app_id}'"
        )
        self._holds[cookie] = ProfileHold(profile, reason, app_id, watch)
        self._controller.switch_profile(profile)
        return cookie

    def remove(self, cookie):
        self._cancel(cookie)
        if len(self._holds) != 0:
            new_profile = self._effective_hold_profile()
        else:
            new_profile = self._controller.base_profile
        self._controller.switch_profile(new_profile)

    def clear(self):
        for cookie in self._holds:
            self._cancel(cookie)


class Controller(exports.interfaces.ExportableInterface):
    def __init__(self, bus, tuned_interface):
        super(Controller, self).__init__()
        self._bus = bus
        self._tuned_interface = tuned_interface
        self._base_profile = PPDProfile.BALANCED
        self._profile_holds = ProfileHoldManager(self)
        self.switch_profile(self._base_profile)

    @property
    def bus(self):
        return self._bus

    @property
    def base_profile(self):
        return self._base_profile

    def switch_profile(self, profile):
        if self.active_profile() == profile:
            return
        tuned_profile = PPD_TO_TUNED[profile]
        log.info(f"Switching to profile '{profile}'")
        self._tuned_interface.switch_profile(tuned_profile)

    def active_profile(self):
        tuned_profile = self._tuned_interface.active_profile()
        return TUNED_TO_PPD[tuned_profile]

    @exports.export("sss", "u")
    def HoldProfile(self, profile, reason, app_id, caller):
        if profile != PPDProfile.POWER_SAVER and profile != PPDProfile.PERFORMANCE:
            raise dbus.exceptions.DBusException(
                f"Only '{PPDProfile.POWER_SAVER}' and '{PPDProfile.PERFORMANCE}' profiles may be held"
            )
        return self._profile_holds.add(profile, reason, app_id, caller)

    @exports.export("u", "")
    def ReleaseProfile(self, cookie, caller):
        if cookie not in self._profile_holds.holds:
            raise dbus.exceptions.DBusException(f"No active hold for cookie '{cookie}'")
        self._profile_holds.remove(cookie)

    @exports.signal("u")
    def ProfileReleased(self, cookie):
        pass

    @exports.set_property("ActiveProfile")
    def set_active_profile(self, profile):
        if profile not in PPDProfile:
            raise dbus.exceptions.DBusException(f"Invalid profile '{profile}'")
        self._base_profile = profile
        self._profile_holds.clear()
        self.switch_profile(profile)

    @exports.get_property("ActiveProfile")
    def get_active_profile(self):
        return self.active_profile()

    @exports.get_property("Profiles")
    def get_profiles(self):
        return dbus.Array([{"Profile": profile, "Driver": DRIVER} for profile in PPDProfile], signature="a{sv}")

    @exports.get_property("Actions")
    def get_actions(self):
        return dbus.Array([], signature="s")

    @exports.get_property("PerformanceDegraded")
    def get_performance_degraded(self):
        return ""

    @exports.get_property("ActiveProfileHolds")
    def get_active_profile_holds(self):
        return dbus.Array(
            [hold.as_dict() for hold in self._profile_holds.holds.values()],
            signature="a{sv}",
        )
