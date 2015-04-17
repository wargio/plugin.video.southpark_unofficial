#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import re
import os
import json
import time
import socket
import urllib
import urllib2
import datetime
import xbmcplugin
import xbmcgui
import xbmcaddon
import xml.etree.ElementTree as ET

addonID = 'plugin.video.southpark_unofficial'
addon = xbmcaddon.Addon(id=addonID)
socket.setdefaulttimeout(30)
pluginhandle = int(sys.argv[1])
icon = xbmc.translatePath('special://home/addons/'+addonID+'/icon.png')
defaultFanart = xbmc.translatePath('special://home/addons/'+addonID+'/fanart.png')
forceViewMode = True
audio_pos = int(addon.getSetting('audio_lang'))
audio = ["EN","ES","DE"]
audio = audio[audio_pos].lower()
audio_links = ["/full-episodes/","/episodios-en-espanol/"]
geolocation_pos = int(addon.getSetting('geolocation'))
geolocation = ["US","UK","ES","DE","IT"]
geolocation = geolocation[geolocation_pos]
viewMode = str("504")

print "GEO %s AUDIO %s" % (geolocation, audio)

def index():
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)
    content = getUrl("http://southpark.cc.com")
    if not "/messages/geoblock/" in content and not "/geoblock/messages/" in content:
        addDir(translation(30005), "Featured", 'listVideos', icon)
        addLink(translation(30006), "Random", 'listVideos', icon)
        for i in range(1, 19):
            addDir(translation(30007)+" "+str(i), 'season-'+str(i), 'listVideos', icon)
        xbmcplugin.endOfDirectory(pluginhandle)
    else:
        notifyText(translation(30002), 6000)


def listVideos(url):
    xbmcplugin.setContent(pluginhandle, "episodes")
    if url == "Featured":
        jsonrsp = getUrl(getCarousel())
        promojson = json.loads(jsonrsp)
        for episode in promojson['results']:
            addLink(episode['title'], episode['itemId'], 'playVideo', episode['images'], episode['description'], episode['episodeNumber'][0]+episode['episodeNumber'][1], episode['episodeNumber'][2]+episode['episodeNumber'][3],episode['originalAirDate'])
    elif url == "Random":
		notifyText(translation(30003), 2000)
		rand = getUrl("http://southpark.cc.com/full-episodes/random").split("<link rel=\"canonical\" href=\"")[1].split("\" />")[0]
		rand = rand.split("http://southpark.cc.com/full-episodes/s")[1].split("-")[0]
		rand = rand.split("e")
		jsonrsp = getUrl("http://southpark.cc.com/feeds/carousel/video/57baee9c-b611-4260-958b-05315479a7fc/30/1/json/!airdate/season-"+str(int(rand[0])))
		seasonjson = json.loads(jsonrsp)
		ep = int(rand[1])-1
		print ep
		episode = seasonjson['results'][ep]
		addLink(episode['title'], episode['itemId'], 'playVideo', episode['images'], episode['description'], episode['episodeNumber'][0]+episode['episodeNumber'][1], episode['episodeNumber'][2]+episode['episodeNumber'][3],episode['originalAirDate'])
    else:
        xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_EPISODE)
        jsonrsp = getUrl("http://southpark.cc.com/feeds/carousel/video/57baee9c-b611-4260-958b-05315479a7fc/30/1/json/!airdate/"+url)
        seasonjson = json.loads(jsonrsp)
        for episode in seasonjson['results']:
            addLink(episode['title'], episode['itemId'], 'playVideo', episode['images'], episode['description'], episode['episodeNumber'][0]+episode['episodeNumber'][1], episode['episodeNumber'][2]+episode['episodeNumber'][3],episode['originalAirDate'])
    xbmcplugin.endOfDirectory(pluginhandle)
    xbmc.executebuiltin('Container.SetViewMode('+viewMode+')')

def playTest(url, title, thumbnail):
	notifyText(translation(30009)+" " + title, 3000)
	mediagen = getMediagen(url)
	swfVfy = "http://media.mtvnservices.com/player/prime/mediaplayerprime.2.7.11.swf" 
	flashVer = "WIN 12,0,0,70"
	app = "viacommtvstrm"
	conn = "B:0"
	rtmp = "rtmpe://viacommtvstrmfs.fplive.net:1935/viacommtvstrm"
	pageUrl = "http://media.mtvnservices.com/player/prime/mediaplayerprime.2.7.11.swf?uri=mgid:arc:episode:southparkstudios.com:"+url
	pageUrl += "&type=network&ref=southpark.cc.com&geo="+ geolocation +"&group=entertainment&network=None&device=Other&"
	pageUrl += "CONFIG_URL=http://media.mtvnservices.com/pmt/e1/players/mgid:arc:episode:southparkstudios.com:/context3/config.xml?"
	pageUrl += "uri=mgid:arc:episode:southparkstudios.com:"+url+"&type=network&ref=southpark.cc.com&geo="+ geolocation +"&group=entertainment&network=None&device=Other"
	i = 0
	pl=xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
	pl.clear()
	parts = str(len(mediagen))
	for media in mediagen:
		rtmpe = getRTMPE(media)
		best = len(rtmpe)-1
		playpath = "mp4:"+rtmpe[best]
		videoname = title + " (" + str(i+1) + " of " + parts +")"
		li = xbmcgui.ListItem(videoname, iconImage=thumbnail, thumbnailImage=thumbnail)
		li.setInfo('video', {'Title': videoname})
		li.setProperty('PlayPath', playpath)
		li.setProperty('conn', conn)
		# li.setProperty('rtmp', rtmp)
		li.setProperty('flashVer', flashVer)
		li.setProperty('pageUrl', pageUrl)
		li.setProperty('app', app)
		li.setProperty('SWFPlayer', swfVfy)
		li.setProperty("SWFVerify", "true")
		pl.add(url=rtmp, listitem=li, index=i)
		i += 1
	player = xbmc.Player(xbmc.PLAYER_CORE_DVDPLAYER)
	player.play(pl)
	for s in xrange(1):
		if player.isPlaying():
			break
		time.sleep(1)
	if not player.isPlaying():
		notifyText(translation(30004), 4000)
		player.stop()
		pl.clear()
	while player.isPlaying():
		time.sleep(2)
	player.stop()
	pl.clear()
	return

def translation(id):
    return addon.getLocalizedString(id).encode('utf-8')
	
def notifyText(text, time=5000):
	__addon__       = xbmcaddon.Addon(id=addonID)
	__addonname__   = __addon__.getAddonInfo('name')
	__icon__        = __addon__.getAddonInfo('icon')
	xbmc.executebuiltin('Notification(%s, %s, %d, %s)'%(__addonname__, text, time, __icon__))

def getUrl(url):
	link = ""
	try:
		req = urllib2.Request(url)
		req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 6.1; rv:25.0) Gecko/20100101 Firefox/25.0')
		response = urllib2.urlopen(req)
		link = response.read()
		response.close()
	except urllib2.URLError:
		notifyText(translation(30010), 3000)
		raise
	return link

def addLink(name, url, mode, iconimage, desc="", season="", episode="", date=""):
    u = sys.argv[0]+"?url="+urllib.quote_plus(url)+"&mode="+str(mode)+"&title="+str(name)+"&thumbnail="+str(iconimage)
    convdate = ""
    if date != "":
        convdate = datetime.datetime.fromtimestamp(int(date)).strftime('%Y-%m-%d %H:%M:%S')
    ok = True
    liz = xbmcgui.ListItem(name, iconImage="DefaultVideo.png", thumbnailImage=iconimage)
    liz.setInfo(type="Video", infoLabels={"Title": name, "Plot": desc, "Season": season, "Episode": episode, "Aired": convdate})
    liz.setProperty("fanart_image", defaultFanart)
    ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=True)
    return ok


def addDir(name, url, mode, iconimage):
    u = sys.argv[0]+"?url="+urllib.quote_plus(url)+"&mode="+str(mode)
    ok = True
    liz = xbmcgui.ListItem(name, iconImage="DefaultFolder.png", thumbnailImage=iconimage)
    liz.setInfo(type="Video", infoLabels={"Title": name})
    liz.setProperty("fanart_image", defaultFanart)
    ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=True)
    return ok

def getCarousel():
	html = getUrl("http://southpark.cc.com/")
	html = html.split("</section><section class=")
	data_url = html[1].split("data-url=\"")
	data_url = data_url[1]
	data_url = data_url.split("\"")[0]
	carousel = data_url.split("{resultsPerPage}/{currentPage}/json/{sort}")[0]
	carousel += "14/1/json/airdate"
	carousel += data_url.split("{resultsPerPage}/{currentPage}/json/{sort}")[1]
	return "http://southpark.cc.com" + carousel

def getMediagen(id):
	feed = getUrl("http://southpark.cc.com/feeds/video-player/mrss/mgid:arc:episode:southparkstudios.com:"+id+"?lang="+audio)
	root = ET.fromstring(feed)
	mediagen = []
	for item in root.iter('guid'):
		if item.text != None:
			mediagen.append(item.text)
	return mediagen

def getRTMPE(mediagen):
	xml = getUrl("http://southpark.cc.com/feeds/player/mediagen?uri="+mediagen+"&device=Other&aspectRatio=16:9&lang="+audio+"&acceptMethods=fms,hdn1,hds")
	parser = ET.XMLParser(encoding="utf-8")
	root = ET.fromstring(xml, parser=parser)
	rtmpe = []
	for item in root.iter('src'):
		if item.text != None:
			rtmpe.append(item.text.split('viacomccstrm/')[1])
	return rtmpe
	
def parameters_string_to_dict(parameters):
    paramDict = {}
    if parameters:
        paramPairs = parameters[1:].split("&")
        for paramsPair in paramPairs:
            paramSplits = paramsPair.split('=')
            if (len(paramSplits)) == 2:
                paramDict[paramSplits[0]] = paramSplits[1]
    return paramDict
	
params = parameters_string_to_dict(sys.argv[2])
mode = urllib.unquote_plus(params.get('mode', ''))
url = urllib.unquote_plus(params.get('url', ''))
eptitle = urllib.unquote_plus(params.get('title', ''))
epthumbnail = urllib.unquote_plus(params.get('thumbnail', ''))

if mode == 'listVideos':
    listVideos(url)
elif mode == 'playVideo':
    playTest(url, eptitle, epthumbnail)
else:
    index()
