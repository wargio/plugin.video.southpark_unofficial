#!/usr/bin/python
# -*- coding: utf-8 -*-
import socket
import southpark

socket.setdefaulttimeout(30)
plugin = southpark.SouthParkAddon(22)
plugin.handle()