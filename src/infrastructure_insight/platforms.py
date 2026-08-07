"""Map catalog platforms to Netmiko device types."""

from .models import Platform


NETMIKO_DEVICE_TYPES = {
    Platform.NXOS: "cisco_nxos",
    Platform.OS10: "dell_os10",
}


def netmiko_device_type(platform: Platform) -> str:
    return NETMIKO_DEVICE_TYPES[platform]
