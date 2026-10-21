import unittest
from seo_check import check_html, allowed, Tags

URL='https://detectaplagas.com.mx/example/'
GOOD='<html><head><title>Example</title><meta name="description" content="Description"><link rel="canonical" href="'+URL+'"></head><body><h1>Example</h1></body></html>'
def run(html=GOOD, status=200, headers=None, redirects=None):
    return check_html(URL, {'body':html,'status':status,'headers':headers or {'Content-Type':'text/html'},'redirects':redirects or [],'final_url':URL})
def codes(*args,**kwargs): return {i['code'] for i in run(*args,**kwargs)[0]}
class Checks(unittest.TestCase):
    def test_clean(self): self.assertEqual(codes(),set())
    def test_missing(self): self.assertEqual(codes('<html></html>'),{'TITLE_MISSING','DESCRIPTION_MISSING','H1_MISSING','CANONICAL_MISSING'})
    def test_multiple(self):
        html=GOOD.replace('</head>','<title>X</title><meta name="description" content="D"><link rel="canonical" href="'+URL+'"></head>').replace('</body>','<h1>Y</h1></body>')
        self.assertEqual(codes(html),{'TITLE_MULTIPLE','DESCRIPTION_MULTIPLE','H1_MULTIPLE','CANONICAL_MULTIPLE'})
    def test_svg_title_not_seo_title(self): self.assertEqual(codes(GOOD.replace('</body>','<svg><title>Icon</title></svg></body>')),set())
    def test_empty(self): self.assertIn('TITLE_EMPTY',codes(GOOD.replace('>Example</title>','></title>')))
    def test_meta_noindex(self): self.assertIn('SITEMAP_NOINDEX',codes(GOOD.replace('</head>','<meta name="robots" content="noindex, follow"></head>')))
    def test_header_noindex(self): self.assertIn('SITEMAP_NOINDEX',codes(headers={'X-Robots-Tag':'googlebot: noindex, follow'}))
    def test_none(self): self.assertIn('SITEMAP_NOINDEX',codes(headers={'X-Robots-Tag':'none'}))
    def test_404_not_missing_metadata(self): self.assertEqual(codes('<h1>404</h1>',status=404),{'HTTP_NON_200'})
    def test_redirect(self): self.assertIn('SITEMAP_REDIRECT',codes(redirects=[{'status':301}]))
    def test_canonical_mismatch(self): self.assertIn('CANONICAL_MISMATCH',codes(GOOD.replace('href="'+URL+'"','href="https://detectaplagas.com.mx/"')))
    def test_relative_canonical(self): self.assertEqual(codes(GOOD.replace('href="'+URL+'"','href="/example/"')),{'CANONICAL_RELATIVE'})
    def test_equivalent_encoded_slug(self):
        u='https://detectaplagas.com.mx/á/'
        r={'body':GOOD.replace(URL,'https://detectaplagas.com.mx/%C3%A1/'),'status':200,'headers':{},'redirects':[],'final_url':u}
        self.assertEqual(check_html(u,r)[0],[])
    def test_template_and_scripts_ignored(self): self.assertEqual(codes(GOOD.replace('</body>','<template><h1>hidden</h1></template><script>"<h1>fake</h1>"</script></body>')),set())
    def test_scope(self):
        self.assertTrue(allowed(URL)); self.assertFalse(allowed('https://detectaplagas.com.mx.evil.test/')); self.assertFalse(allowed('http://detectaplagas.com.mx/')); self.assertFalse(allowed('https://user@detectaplagas.com.mx/'))
    def test_non_html(self): self.assertEqual(codes(headers={'Content-Type':'application/json'}),{'NOT_HTML'})
if __name__=='__main__': unittest.main()
