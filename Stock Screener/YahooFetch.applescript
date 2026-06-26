-- YahooFetch.applescript
-- Helper for the Mid/Smallcap Screener VBA engine (Mac Excel).
-- Install location (exact path, create folders if missing):
--   ~/Library/Application Scripts/com.microsoft.Excel/YahooFetch.applescript
-- The cookie jar in /tmp lets curl handle Yahoo's cookie+crumb handshake natively.

on fetchUrl(theUrl)
	set jar to "/tmp/yfscreener_cookies.txt"
	try
		return do shell script "curl -s -L --max-time 30 --compressed -A 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36' -H 'Accept: application/json,text/plain,*/*' -b " & jar & " -c " & jar & " " & quoted form of theUrl
	on error errMsg
		return ""
	end try
end fetchUrl
