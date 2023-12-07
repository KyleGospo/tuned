from tuned import exports

DRIVER = "TuneD"

PPD_TO_TUNED = {
    "power-saver": "powersave",
    "balanced": "balanced",
    "performance": "throughput-performance",
}

TUNED_TO_PPD = {
    "powersave": "power-saver",
    "balanced": "balanced",
    "throughput-performance": "performance",
}


class Controller(exports.interfaces.ExportableInterface):
    def __init__(self, tuned_interface):
        super(Controller, self).__init__()
        self._tuned_interface = tuned_interface
        self._held_profiles = []

    @exports.export("sss", "u")
    def HoldProfile(self, profile, reason, app_id, caller=None):
        return 0

    @exports.export("s", "")
    def ReleaseProfile(self, cookie, caller=None):
        return

    @exports.set_property("ActiveProfile")
    def set_active_profile(self, profile):
        tuned_profile = PPD_TO_TUNED[profile]
        return self._tuned_interface.switch_profile(tuned_profile)

    @exports.get_property("ActiveProfile")
    def get_active_profile(self):
        tuned_profile = self._tuned_interface.active_profile()
        return TUNED_TO_PPD[tuned_profile]

    @exports.get_property("Profiles")
    def get_profiles(self):
        return [
            {"Profile": profile, "Driver": DRIVER} for profile in PPD_TO_TUNED.keys()
        ]
