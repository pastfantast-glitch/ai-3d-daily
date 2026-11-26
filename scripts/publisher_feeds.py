"""Exact publisher-declared HTTPS feed aliases; never a general redirect bypass.

Article links still have to belong to the registered publisher. HTTPS, public
DNS, redirect and response-size checks apply to the resolved feed as usual.
"""
ALIASES = {
    'https://www.cgchannel.com/feed/': 'https://feeds2.feedburner.com/cgchannel/nHpU',
    'https://www.blendernation.com/feed/': 'https://feeds.feedburner.com/Blendernation',
}


def feed_endpoint(url):
    return ALIASES.get(url, url)
