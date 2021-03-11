#!/usr/bin/python3

import argparse
from urllib.request import Request
from urllib.request import urlopen
from urllib.error import HTTPError
import json
import os
import re
import datetime
import base64

WORKI_DIR  = os.path.dirname(os.path.realpath(__file__))
USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; rv:25.0) Gecko/20100101 Firefox/25.0'
IS_DEBUG   = False

APIS = {
	"en": {
		"language": "en",
		"mediagen": "southparkstudios.com",
		"domain": "https://southparkstudios.com",
		"domapi": "https://southpark.cc.com",
		"uri": "/seasons/south-park/",
		"html_links": False,
		"has_ads": True,
	},
	"es": {
		"language": "es",
		"mediagen": "southparkstudios.com",
		"domain": "https://southpark.cc.com",
		"domapi": "https://southpark.cc.com",
		"uri": "/es/seasons/south-park/",
		"html_links": False,
		"has_ads": True,
	},
	"de": {
		"language": "de",
		"mediagen": "southpark.intl",
		"domain": "https://www.southpark.de",
		"domapi": "https://www.southpark.de",
		"uri": "/seasons/south-park/",
		"html_links": True,
		"has_ads": False,
	},
	"se": {
		"language": "se",
		"mediagen": "southpark.intl",
		"domain": "https://southparkstudios.nu",
		"domapi": "https://www.southparkstudios.nu",
		"uri": "/seasons/south-park/",
		"html_links": False,
		"has_ads": False,
	},
	"eu": {
		"language": "en",
		"mediagen": "southparkstudios.com",
		"domain": "https://www.southparkstudios.com",
		"domapi": "https://southpark.cc.com",
		"uri": "/seasons/south-park/",
		"html_links": False,
		"has_ads": False,
	}
}

def log_debug(msg):
	if IS_DEBUG:
		print("[D] {}".format(msg))

def log_struct(data):
	if IS_DEBUG:
		print(json.dumps(data, indent=4))

def _http_get(url, is_json=False):
	if len(url) < 1:
		return None
	req = Request(url)
	req.add_header('User-Agent', USER_AGENT)
	response = urlopen(req)
	data = response.read()
	response.close()
	data = data.decode("utf-8")
	if is_json:
		data = json.loads(data, strict=False)
	log_debug("http get: {0}".format(url))
	return data

def write_data(path, data):
	with open(path,'w') as output:
		output.truncate()
		output.write(data)

def write_json(path, data):
	with open(path, 'w') as fp:
		fp.truncate()
		json.dump(data, fp, indent=4)

def _dk(obj, keys, default=None):
	if not isinstance(obj, list) and not isinstance(obj, dict):
		return default
	for k in keys:
		if not isinstance(k, int) and "|" in k and isinstance(obj, list):
			t = k.split("|")
			found = None
			for o in obj:
				if t[0] not in o:
					return default
				elif o[t[0]] == t[1]:
					found = o
					break
			if found == None:
				log_debug("not found: {} -> {}".format(k, keys).replace("'", '"'))
				return default
			obj = found
		elif isinstance(obj, dict) and k not in obj:
			log_debug("not found: {} -> {}".format(k, keys).replace("'", '"'))
			return default
		elif isinstance(obj, list) and isinstance(k, int) and k >= len(obj):
			log_debug("not found: {} -> {}".format(k, keys).replace("'", '"'))
			return default
		else:
			obj = obj[k]
	return obj

def _make_episode(data, season, episode, lang):
	has_ads  = APIS[lang]["has_ads"]
	domapi   = APIS[lang]["domapi"]
	mediagen = APIS[lang]["mediagen"]

	ep = {
		"image":   _dk(data, ["media", "image", "url"], ""),
		"uuid":    _dk(data, ["id"], ""),
		"details": _dk(data, ["meta", "description"], ""),
		"date":    _dk(data, ["meta", "date"], ""),
		"title":   _dk(data, ["meta", "subHeader"], ""),
		"url":     _dk(data, ["url"], ""),
		"season":  "{}".format(season  + 1),
		"episode": "{}".format(episode + 1),
		"mediagen": []
	}

	try:
		args = "uri=mgid:arc:episode:{mediagen}:{uuid}&configtype=edge&ref={dom}{ref}".format(mediagen=mediagen, uuid=ep["uuid"], dom=domapi, ref=ep["url"])
		url  = "https://media.mtvnservices.com/pmt/e1/access/index.html?{args}".format(args=args)
		service = _http_get(url, True)
		url = service["seamlessMediaGen"].replace('/{uri}/', "/" + service["uri"] + "/")
		urls = []
		try:
			if len(url) > 0:
				_http_get(url, True)
				urls = [url]
		except HTTPError:
			urls = []
		if len(urls) < 1 or has_ads:
			items = _dk(service, ["feed", "items"], [])
			i = 0
			for url in items:
				items[i] = _dk(url, ["group", "content"], "").replace("&device={device}", "") + "&format=json&acceptMethods=hls"
				i += 1
			if len(items) > 0:
				urls = items
		ep["mediagen"] = urls
	except HTTPError as e:
		log_debug("http get: {0} {1}".format(url, e))

	ep["mediagen"] = list(filter(None, ep["mediagen"]))

	print("s{:<2}e{:<2} len:{}: {}".format(ep["season"], ep["episode"], len(ep["mediagen"]), ep["title"]))
	i = 0
	for url in ep["mediagen"]:
		ep["mediagen"][i] = base64.b64encode(url.encode('ascii')).decode('ascii')
		i += 1
	log_struct(ep)

	return ep

def _has_extra(x):
	return "loadMore" in x and x["loadMore"] != None and "type" in x and x["type"] == "video-guide"

def _parse_episodes(data, season, lang):
	domapi = APIS[lang]["domapi"]
	print("parsing episodes from season", season + 1)
	extra = []
	lists = _dk(data,["children", "type|MainContainer", "children"], [])
	if lang in ["en", "es", "eu"]:
		lists = list(filter(lambda x: "type" in x and x["type"] == "LineList", lists))
		extra = list(filter(lambda x: _has_extra(x), [ _dk(s, ["props"], []) for s in lists ]))
		lists = list(filter(lambda x: len(x) > 0 and "url" in x[0], [ _dk(s, ["props", "items"], []) for s in lists ]))[0]
	elif lang in ["se", "de"]:
		lists = list(filter(lambda x: "type" in x and x["type"] == "LineList" and "type" in x["props"] and x["props"]["type"] == "video-guide", lists))
		if _dk(lists[0], ["props", "loadMore", "url"], "") != "":
			extra.append(_dk(lists[0], ["props"], {}))
		lists = _dk(lists[0], ["props", "items"], [])
		if len(lists) > 0 and _dk(lists[0], ["meta", "subHeader"], None) == None:
			return []
	else:
		return []


	lists = [_make_episode(lists[i], season, i, lang) for i in range(0, len(lists))]

	if len(extra) > 0:
		url = _dk(extra[0], ["loadMore", "url"], "")
		if len(url) > 0:
			extra = _http_get(domapi + url, True)
			lists.extend([_make_episode(extra["items"][i], season, i + len(lists), lang) for i in range(0, len(extra["items"]))])
		else:
			raise Exception("Cannot fetch all episodes")
	return lists

def _download_data(url, html_links):
	webpage = _http_get(url)
	if IS_DEBUG:
		write_data("debug-data.html", webpage)

	if "window.__DATA__" in webpage:
		dataidx  = webpage.index("window.__DATA__")
		data     = webpage[dataidx:]
		endidx   = data.index("};")
		equalidx = data.index("=")
		data     = data[equalidx + 1:endidx + 1].strip()
		data     = json.loads(data, strict=False)

		if IS_DEBUG:
			write_json("debug-data.json", data)

		if html_links:
			links = re.findall(r"href=\"/seasons/south-park/[\w]+/[\w]+-\d+", webpage, flags=re.M)
			links = [x.split('"')[1] for x in links]
			data["links_found"] = [None]
			data["links_found"].extend(links)
		return data
	return None

def generate_data(lang):
	domain     = APIS[lang]["domain"]
	uri        = APIS[lang]["uri"]
	html_links = APIS[lang]["html_links"]

	data = _download_data(domain + uri, html_links)
	main = _dk(data,["children", "type|MainContainer", "children"])
	seasons_urls = []
	if "links_found" in data:
		log_debug("using links")
		seasons_urls = data["links_found"]
	else:
		seasons_urls = [ _dk(s, ["url"]) for s in _dk(main, ["type|SeasonSelector", "props", "items"], [])]

	log_debug("seasons: {}".format(len(seasons_urls)))

	seasons = []

	index = 0
	for url in seasons_urls:
		index += 1
		if url != None:
			data = _download_data(domain + url, False)
		lists = _parse_episodes(data, len(seasons_urls) - index, lang)
		if len(lists) < 1 and len(seasons) < 1:
			continue
		seasons.append(lists)

	seasons.reverse()
	return {
		"created": "{}".format(datetime.datetime.now()),
		"seasons": seasons
	}	

def generate_file(lang):
	data = generate_data(lang)
	write_json("addon-data-{}.json".format(lang), data)

def main():
	global IS_DEBUG

	parser = argparse.ArgumentParser()
	parser.add_argument('--debug', action='store_true', default=False, help='enable debug')
	group = parser.add_mutually_exclusive_group(required=True)
	group.add_argument('--en', action='store_true', default=False, help='language english (north america)')
	group.add_argument('--es', action='store_true', default=False, help='language spanish (north america)')
	group.add_argument('--de', action='store_true', default=False, help='language german (germany)')
	group.add_argument('--se', action='store_true', default=False, help='language swedish (sweden)')
	group.add_argument('--eu', action='store_true', default=False, help='language english (europe)')
	args = parser.parse_args()

	os.chdir(WORKI_DIR)

	IS_DEBUG = args.debug

	if args.en:
		generate_file("en")
	elif args.es:
		generate_file("es")
	elif args.de:
		generate_file("de")
	elif args.se:
		generate_file("se")
	elif args.eu:
		generate_file("eu")
	else:
		print("nothing was selected..")

if __name__ == '__main__':
	main()
