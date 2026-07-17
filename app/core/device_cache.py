class DeviceCache:

    def __init__(self):

        self.devices = []

    def update(self, devices):

        self.devices = list(devices)

    def all(self):

        return self.devices

    def count(self):

        return len(self.devices)

    def clear(self):

        self.devices.clear()