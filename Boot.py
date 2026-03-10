import usb_hid

# Enable all HID devices needed by Pico Web HID
# This file must exist on CIRCUITPY root.
# After creating or editing this file, unplug and replug the USB cable.

usb_hid.enable((
    usb_hid.Device.MOUSE,
    usb_hid.Device.KEYBOARD,
    usb_hid.Device.CONSUMER_CONTROL,
))
