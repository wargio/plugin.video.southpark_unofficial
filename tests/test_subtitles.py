import unittest

from subtitles import (
	SubtitleError,
	build_subtitles,
	find_subtitle_playlist,
	merge_segments,
	segment_urls,
)


MASTER = """#EXTM3U
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio0",NAME="American English",DEFAULT=YES,URI="audio/index.m3u8"
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs0",NAME="American English",LANGUAGE="en",AUTOSELECT=YES,DEFAULT=YES,URI="hdntl=exp=1~acl=%2f*~hmac=ab/index-f9.m3u8"
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs0",NAME="Deutsch, Untertitel",LANGUAGE="de",AUTOSELECT=YES,DEFAULT=NO,URI="index-f10.m3u8"
#EXT-X-STREAM-INF:BANDWIDTH=907671,RESOLUTION=640x360,AUDIO="audio0",SUBTITLES="subs0"
index-f1.m3u8
"""

MASTER_URL = "https://cdn.example.test/h/a/token/master.m3u8"

PLAYLIST = """#EXTM3U
#EXT-X-TARGETDURATION:5
#EXT-X-PLAYLIST-TYPE:VOD
#EXTINF:4.000,
https://subs.example.test/segment-1-f9.vtt
#EXT-X-DISCONTINUITY
#EXTINF:4.000,
segment-2-f9.vtt
#EXT-X-ENDLIST
"""

SEGMENT_EMPTY = "WEBVTT\r\n\r\n"

SEGMENT_1 = """WEBVTT\r\n\r\n00:00:01.000 --> 00:00:03.000 position:50% align:middle line:100%\r\n<b>First line.</b>\r\n\r\n00:00:03.500 --> 00:00:05.000 position:50% align:middle line:100%\r\n<b>Spans the boundary.</b>\r\n"""

SEGMENT_2 = """WEBVTT\n\nNOTE a comment\n\n00:00:03.500 --> 00:00:05.000 position:50% align:middle line:100%\n<b>Spans the boundary.</b>\n\ncue-7\n00:00:06.000 --> 00:00:07.000\nTwo\nlines.\n"""


class FindSubtitlePlaylistTests(unittest.TestCase):
	def test_prefers_region_language(self):
		url, language = find_subtitle_playlist(MASTER, MASTER_URL, "de")
		self.assertEqual(url, "https://cdn.example.test/h/a/token/index-f10.m3u8")
		self.assertEqual(language, "de")

	def test_falls_back_to_default_rendition(self):
		url, language = find_subtitle_playlist(MASTER, MASTER_URL, "br")
		self.assertEqual(url, "https://cdn.example.test/h/a/token/hdntl=exp=1~acl=%2f*~hmac=ab/index-f9.m3u8")
		self.assertEqual(language, "en")

	def test_quoted_attribute_with_comma(self):
		url, _ = find_subtitle_playlist(MASTER, MASTER_URL, "de")
		self.assertTrue(url.endswith("index-f10.m3u8"))

	def test_no_subtitle_rendition(self):
		self.assertEqual(find_subtitle_playlist("#EXTM3U\nindex-f1.m3u8\n", MASTER_URL, "en"), (None, None))


class SegmentUrlTests(unittest.TestCase):
	def test_resolves_absolute_and_relative_urls(self):
		urls = segment_urls(PLAYLIST, "https://cdn.example.test/subs/index-f9.m3u8")
		self.assertEqual(urls, [
			"https://subs.example.test/segment-1-f9.vtt",
			"https://cdn.example.test/subs/segment-2-f9.vtt",
		])


class MergeSegmentsTests(unittest.TestCase):
	def test_merges_and_deduplicates_cues(self):
		merged = merge_segments([SEGMENT_EMPTY, SEGMENT_1, SEGMENT_2])
		self.assertTrue(merged.startswith("WEBVTT\n\n"))
		self.assertEqual(merged.count("Spans the boundary."), 1)
		self.assertNotIn("NOTE", merged)
		self.assertNotIn("\r", merged)
		self.assertIn("00:00:06.000 --> 00:00:07.000\nTwo\nlines.", merged)
		self.assertLess(merged.index("First line."), merged.index("Two"))

	def test_rejects_track_without_cues(self):
		with self.assertRaises(SubtitleError):
			merge_segments([SEGMENT_EMPTY, SEGMENT_EMPTY])

	def test_rejects_timestamp_map(self):
		with self.assertRaises(SubtitleError):
			merge_segments(["WEBVTT\nX-TIMESTAMP-MAP=MPEGTS:900000,LOCAL:00:00:00.000\n\n00:00:01.000 --> 00:00:02.000\nHi\n"])


class BuildSubtitlesTests(unittest.TestCase):
	def test_end_to_end(self):
		responses = {
			MASTER_URL: MASTER,
			"https://cdn.example.test/h/a/token/hdntl=exp=1~acl=%2f*~hmac=ab/index-f9.m3u8": PLAYLIST,
			"https://subs.example.test/segment-1-f9.vtt": SEGMENT_1,
			"https://cdn.example.test/h/a/token/hdntl=exp=1~acl=%2f*~hmac=ab/segment-2-f9.vtt": SEGMENT_2,
		}
		vtt, language = build_subtitles(MASTER_URL, "eu", responses.__getitem__)
		self.assertEqual(language, "en")
		self.assertEqual(vtt.count("-->"), 3)

	def test_stream_without_subtitles(self):
		self.assertEqual(build_subtitles(MASTER_URL, "en", lambda url: "#EXTM3U\n"), (None, None))


if __name__ == "__main__":
	unittest.main()
