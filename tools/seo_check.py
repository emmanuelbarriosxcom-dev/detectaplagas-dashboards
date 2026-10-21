#!/usr/bin/env python3
"""F28: bounded, anonymous, sequential SEO checks. Python standard library only."""
import argparse
import csv
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

SITE = 'https://detectaplagas.com.mx'
SITEMAP = SITE + '/sitemap_index.xml'
UA = 'DetectaF28SEOCheck/1.0 (+https://github.com/emmanuelbarriosxcom-dev/detectaplagas-dashboards)'
MAX_BYTES = 8 * 1024 * 1024

def allowed(url):
    p = urllib.parse.urlsplit(url)
    return p.scheme == 'https' and p.hostname == 'detectaplagas.com.mx' and p.port in (None, 443) and not p.username and not p.password

def normal(url):
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), urllib.parse.unquote(p.path or '/'), p.query, ''))

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        self.hops = []
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            raise ValueError('Redirect outside approved HTTPS host: ' + newurl)
        self.hops.append({'status': code, 'from': req.full_url, 'to': newurl})
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def fetch(url):
    if not allowed(url):
        raise ValueError('URL outside approved host: ' + url)
    redirects = SafeRedirect()
    opener = urllib.request.build_opener(redirects)
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml,application/xml,text/xml;q=0.9,*/*;q=0.5'})
    try:
        response = opener.open(req, timeout=25)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('Response exceeded 8 MiB; not fully checked')
        headers = response.headers
        return {'status': response.code, 'final_url': response.geturl(), 'redirects': redirects.hops,
                'headers': dict(headers), 'body': raw.decode(headers.get_content_charset() or 'utf-8', errors='replace'),
                'sha256': hashlib.sha256(raw).hexdigest()}

class Tags(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.head = False
        self.titles = []
        self.descriptions = []
        self.canonicals = []
        self.robots = []
        self.h1 = []
        self.capture = None
        self.ignored = 0
        self.base = None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'head': self.head = True
        if tag in ('script', 'style', 'template'): self.ignored += 1
        if self.ignored: return
        if tag == 'base' and self.head and self.base is None: self.base = a.get('href')
        if tag == 'title' and self.head:
            self.titles.append(''); self.capture = ('title', len(self.titles)-1)
        if tag == 'h1':
            self.h1.append(''); self.capture = ('h1', len(self.h1)-1)
        if tag == 'meta':
            name = a.get('name', '').lower()
            if name == 'description': self.descriptions.append(a.get('content', ''))
            if name in ('robots', 'googlebot'): self.robots.append(a.get('content', ''))
        if tag == 'link' and 'canonical' in a.get('rel', '').lower().split(): self.canonicals.append(a.get('href', ''))
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'template'):
            self.ignored = max(0, self.ignored-1)
        if tag == 'head': self.head = False
        if self.capture and tag == self.capture[0]: self.capture = None
    def handle_data(self, data):
        if self.capture and not self.ignored:
            kind, i = self.capture
            (self.titles if kind == 'title' else self.h1)[i] += data


def check_html(url, response):
    issues = []
    def issue(code, severity, detail): issues.append({'code': code, 'severity': severity, 'detail': detail})
    if response['status'] != 200:
        issue('HTTP_NON_200', 'Alta', 'HTTP ' + str(response['status']) + '; verify transport/WAF before interpreting HTML')
        return issues, {}
    if response['redirects']:
        issue('SITEMAP_REDIRECT', 'Media', json.dumps(response['redirects'], ensure_ascii=False))
    ctype = next((v for k,v in response['headers'].items() if k.lower() == 'content-type'), '')
    if ctype and 'html' not in ctype.lower():
        issue('NOT_HTML', 'Alta', ctype); return issues, {}
    tags = Tags(); tags.feed(response['body'])
    for name, values in [('TITLE',tags.titles), ('DESCRIPTION',tags.descriptions), ('H1',tags.h1), ('CANONICAL',tags.canonicals)]:
        if not values: issue(name+'_MISSING', 'Alta' if name == 'CANONICAL' else 'Media', 'No element found in server HTML')
        elif len(values) > 1: issue(name+'_MULTIPLE', 'Alta' if name == 'CANONICAL' else 'Media', str(len(values))+' elements within this page')
        if values and any(not v.strip() for v in values): issue(name+'_EMPTY','Media','Empty value')
    if len(tags.canonicals) == 1 and tags.canonicals[0].strip():
        canonical = urllib.parse.urljoin(urllib.parse.urljoin(response['final_url'],tags.base or ''),tags.canonicals[0])
        if normal(canonical) != normal(url):
            issue('CANONICAL_MISMATCH','Alta','Declared '+canonical+'; sitemap expects self canonical (review intentional exceptions)')
        if not urllib.parse.urlsplit(tags.canonicals[0]).scheme:
            issue('CANONICAL_RELATIVE','Baja','Relative canonical; resolves to '+canonical)
    robot_values = list(tags.robots)
    robot_values += [v for k,v in response['headers'].items() if k.lower() == 'x-robots-tag']
    if any(re.search(r'(?i)(?:^|[\s,:;])(noindex|none)(?:$|[\s,;])', v) for v in robot_values):
        issue('SITEMAP_NOINDEX','Alta','Unexpected noindex in sitemap: '+ '; '.join(robot_values))
    evidence = {'titles':tags.titles, 'descriptions':tags.descriptions, 'h1':tags.h1, 'canonicals':tags.canonicals, 'robots':robot_values}
    return issues, evidence

def discover(delay, limit, out):
    queue = [SITEMAP]; seen = set(); urls = []; evidence = []
    while queue:
        url = queue.pop(0)
        if url in seen: continue
        if len(seen) >= 30: raise ValueError('Sitemap limit exceeded; incomplete')
        seen.add(url); r = fetch(url)
        evidence.append({k:v for k,v in r.items() if k != 'body'} | {'url':url})
        if r['status'] != 200: raise ValueError('Sitemap HTTP '+str(r['status'])+' at '+url)
        root = ET.fromstring(r['body'])
        kind = root.tag.rsplit('}',1)[-1]
        locs = [e.text.strip() for e in root.findall('./{*}sitemap/{*}loc' if kind == 'sitemapindex' else './{*}url/{*}loc') if e.text]
        if kind not in ('sitemapindex','urlset'): raise ValueError('Invalid sitemap root '+kind)
        for loc in locs:
            if not allowed(loc): raise ValueError('Unexpected sitemap host '+loc)
            if kind == 'sitemapindex': queue.append(loc)
            elif loc not in urls: urls.append(loc)
        if len(urls) > limit: raise ValueError('URL limit exceeded; incomplete')
        (out/'sitemaps.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
        time.sleep(delay)
    if not urls: raise ValueError('Sitemap contains no URLs; incomplete')
    return urls

def write_report(out, rows, global_errors, started):
    issues = [{'url':r['url'], **i} for r in rows for i in r['issues']]
    data = {'started_utc':started,'finished_utc':datetime.now(timezone.utc).isoformat(), 'scope':SITEMAP,
            'urls_checked':len(rows), 'complete':not global_errors,'global_errors':global_errors,
            'issues_count':len(issues),'urls_with_issues':sum(bool(r['issues']) for r in rows),'pages':rows}
    (out/'report.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    with (out/'issues.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=['url','severity','code','detail']); w.writeheader(); w.writerows(issues)
    lines=['# Detecta Plagas · F28', '', 'UTC: '+started, '', f"URLs comprobadas: {len(rows)}. Incidencias: {len(issues)}. Completo: {not global_errors}.", '', '## Problemas de ejecución'] + (['- '+e for e in global_errors] or ['Ninguno.'])
    lines += ['', '## Hallazgos', '', '| URL | Gravedad | Problema | Evidencia |','|---|---|---|---|']
    for i in issues:
        lines.append('| '+' | '.join(str(i[k]).replace('|',' / ').replace('\n',' ') for k in ['url','severity','code','detail'])+' |')
    if not issues: lines.append('| — | — | Sin incidencias detectadas en esta ejecución | Véase alcance y limitaciones |')
    lines += ['', '## Alcance', 'GET secuenciales sin sesión. HTML entregado por servidor; no ejecuta JavaScript, no sustituye GSC ni verifica indexación real. Cuenta etiquetas por página, no duplicados entre URLs. Canonical esperado: la propia URL del sitemap; una excepción intencional requiere revisión humana. No reintenta ni evade un 403/406/429. No modifica el sitio.']
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in data.items() if k != 'pages'},ensure_ascii=False,indent=2))
    return 2 if global_errors else (1 if issues else 0)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--output',default='reports/f28'); p.add_argument('--delay',type=float,default=1.0); p.add_argument('--max-urls',type=int,default=250)
    args=p.parse_args(); out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    started=datetime.now(timezone.utc).isoformat(); rows=[]; errors=[]
    try:
        urls=discover(max(1.0,args.delay),args.max_urls,out)
        (out/'urls.txt').write_text('\n'.join(urls)+'\n',encoding='utf-8')
        for url in urls:
            try:
                r=fetch(url); issues,evidence=check_html(url,r)
                rows.append({'url':url,'status':r['status'],'final_url':r['final_url'],'redirects':r['redirects'],'sha256':r['sha256'],'evidence':evidence,'issues':issues})
            except Exception as exc:
                rows.append({'url':url,'status':None,'issues':[{'code':'FETCH_FAILED','severity':'Alta','detail':str(exc)}]})
            print(url,rows[-1].get('status'),len(rows[-1]['issues']),flush=True)
            time.sleep(max(1.0,args.delay))
    except Exception as exc: errors.append(str(exc))
    return write_report(out,rows,errors,started)

if __name__ == '__main__': sys.exit(main())
