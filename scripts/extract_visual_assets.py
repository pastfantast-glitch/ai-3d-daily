#!/usr/bin/env python3
import io, json, re, sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / 'assets' / 'visual'
OUT_DIR.mkdir(parents=True, exist_ok=True)
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36'
TIMEOUT = 25
BAD = re.compile(r'(logo|icon|avatar|author|cookie|banner|advert|ads|sprite|placeholder|zoom-icon|tracking|pixel|emoji)', re.I)
GOOD = re.compile(r'(final|render|hero|cover|scene|character|portrait|environment|unreal|blender|result|project|screenshot|preview)', re.I)


def latest_date():
    dates = sorted(p.stem for p in (ROOT/'data'/'daily').glob('20??-??-??.json'))
    if not dates:
        raise SystemExit('No canonical daily datasets found')
    return dates[-1]


def load_entries(date):
    data = json.loads((ROOT/'data'/'daily'/f'{date}.json').read_text('utf-8'))
    entries = []
    for intel_id, cfg in (data.get('visual_evidence') or {}).items():
        if cfg.get('enabled', True) is False:
            continue
        page_url = cfg.get('source_url')
        if not page_url:
            continue
        entries.append({
            'id': intel_id,
            'page_url': page_url,
            'keywords': cfg.get('keywords', []),
            'label': cfg.get('label', 'SOURCE PREVIEW'),
            'confidence': cfg.get('confidence', 'candidate')
        })
    return entries


def norm_url(base, value):
    if not value:
        return None
    value = value.strip()
    if value.startswith('//'):
        value = 'https:' + value
    return urljoin(base, value)


def srcset_best(base, value):
    if not value:
        return None
    parts=[]
    for chunk in value.split(','):
        bits=chunk.strip().split()
        if not bits:
            continue
        u=norm_url(base,bits[0]); weight=0
        if len(bits)>1:
            m=re.match(r'(\d+)(w|x)',bits[1])
            if m:
                weight=int(m.group(1))
        parts.append((weight,u))
    return max(parts,default=(0,None))[1]


def collect_candidates(page_url, html, keywords):
    soup=BeautifulSoup(html,'html.parser'); found={}
    def add(url,score,reason,context=''):
        url=norm_url(page_url,url)
        if not url or not url.startswith(('http://','https://')):
            return
        text=f'{url} {context}'
        if BAD.search(text): score-=120
        if GOOD.search(text): score+=22
        for k in keywords:
            if str(k).lower() in text.lower(): score+=8
        prev=found.get(url)
        if not prev or score>prev['score']:
            found[url]={'url':url,'score':score,'reason':reason,'context':context[:300]}

    for prop,score in [('og:image',110),('twitter:image',102),('twitter:image:src',102)]:
        tag=soup.find('meta',attrs={'property':prop}) or soup.find('meta',attrs={'name':prop})
        if tag: add(tag.get('content'),score,prop)

    for script in soup.find_all('script',type='application/ld+json'):
        try: data=json.loads(script.string or '{}')
        except Exception: continue
        stack=[data]
        while stack:
            obj=stack.pop()
            if isinstance(obj,dict):
                if 'image' in obj:
                    imgs=obj['image'] if isinstance(obj['image'],list) else [obj['image']]
                    for v in imgs:
                        if isinstance(v,str): add(v,92,'jsonld:image')
                        elif isinstance(v,dict): add(v.get('url') or v.get('contentUrl'),92,'jsonld:image')
                stack.extend(obj.values())
            elif isinstance(obj,list): stack.extend(obj)

    for img in soup.find_all('img'):
        context=' '.join(filter(None,[img.get('alt',''),img.get('title',''),img.get('class') and ' '.join(img.get('class'))]))
        for attr,score in [('data-src',78),('data-lazy-src',78),('data-original',78),('src',70)]:
            add(img.get(attr),score,f'img:{attr}',context)
        ss=srcset_best(page_url,img.get('srcset') or img.get('data-srcset'))
        if ss: add(ss,84,'img:srcset',context)
    return sorted(found.values(),key=lambda x:x['score'],reverse=True)


def fetch_image(session,page_url,cand):
    r=session.get(cand['url'],timeout=TIMEOUT,headers={'Referer':page_url},allow_redirects=True)
    r.raise_for_status()
    if 'image' not in r.headers.get('content-type','').lower():
        raise ValueError('candidate is not an image')
    im=Image.open(io.BytesIO(r.content)); im.load(); w,h=im.size
    if w<640 or h<320:
        raise ValueError(f'too small {w}x{h}')
    ratio=w/h; area=w*h
    score=cand['score']+min(45,area/350000)+(8 if 1.1<=ratio<=2.2 else 0)
    return im,score


def save_image(intel_id,im):
    if im.mode not in ('RGB','L'):
        bg=Image.new('RGB',im.size,(18,24,39))
        if 'A' in im.getbands(): bg.paste(im,mask=im.getchannel('A'))
        else: bg.paste(im)
        im=bg
    else:
        im=im.convert('RGB')
    if im.width>1600:
        nh=round(im.height*1600/im.width)
        im=im.resize((1600,nh),Image.Resampling.LANCZOS)
    out=OUT_DIR/f'{intel_id}.jpg'
    im.save(out,'JPEG',quality=88,optimize=True,progressive=True)
    return out


def main():
    date=sys.argv[1] if len(sys.argv)>1 else latest_date()
    entries=load_entries(date)
    session=requests.Session(); session.headers.update({'User-Agent':UA,'Accept-Language':'en-US,en;q=0.8'})
    report={'date':date,'identity':'data-intel-id','generated_by':'scripts/extract_visual_assets.py','entries':[]}
    for entry in entries:
        rec={'id':entry['id'],'page_url':entry['page_url'],'status':'missing','confidence':entry['confidence']}
        try:
            page=session.get(entry['page_url'],timeout=TIMEOUT); page.raise_for_status()
            candidates=collect_candidates(entry['page_url'],page.text,entry['keywords'])
            winner=None; tested=[]
            for cand in candidates[:18]:
                try:
                    im,score=fetch_image(session,entry['page_url'],cand)
                    tested.append({'url':cand['url'],'score':round(score,2),'size':list(im.size),'reason':cand['reason']})
                    if winner is None or score>winner[0]: winner=(score,cand,im.copy())
                except Exception:
                    continue
            if not winner:
                raise RuntimeError('no valid representative image candidate')
            score,cand,im=winner
            out=save_image(entry['id'],im)
            rec.update({'status':'ok','asset_path':str(out.relative_to(ROOT)).replace('\\','/'),'source_image_url':cand['url'],'source_kind':cand['reason'],'width':im.width,'height':im.height,'label':entry['label'],'score':round(score,2),'tested':tested[:8]})
        except Exception as exc:
            rec['error']=str(exc)
        report['entries'].append(rec)
    (OUT_DIR/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    ok=sum(x['status']=='ok' for x in report['entries'])
    print(f'visual assets {date}: {ok}/{len(report["entries"])}')
    if entries and ok==0:
        raise SystemExit(2)

if __name__=='__main__': main()
