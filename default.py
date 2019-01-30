#!/usr/bin/python
# -*- coding: utf-8 -*-
import socket
import southpark

socket.setdefaulttimeout(30)
southpark.set_xbmc(xbmc)
plugin = southpark.SouthParkAddon('plugin.video.southpark_unofficial', notifyText, 22)
plugin.handle()