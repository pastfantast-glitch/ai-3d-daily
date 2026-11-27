"""Category navigation rules; collection admission still requires production relevance."""
import re
from urllib.parse import urlsplit

BUILTINS = {'ai-generation','3d-production','3d-animation','engine-art','emerging-case','blender-dcc'}
FIELDS = {'id','name','description','enabled','visible','hide_empty','order','include_terms','exclude_terms','source_ids','manual_urls','excluded_urls'}

def validate_navigation(rows, sources):
    def need(ok, message):
        if not ok: raise ValueError('Category navigation: '+message)
    need(isinstance(rows,list) and 1 <= len(rows) <= 30, '1–30 categories required')
    ids=set(); source_ids={s['id'] for s in sources}
    for c in rows:
        need(isinstance(c,dict) and set(c)==FIELDS, 'invalid fields')
        cid=c['id']
        need(isinstance(cid,str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{1,47}',cid) and cid not in ids and cid not in {'top5','ai-3d','history','admin','saved','topics','categories'}, 'invalid ID')
        ids.add(cid)
        for key,limit,empty in [('name',80,False),('description',500,True)]:
            v=c[key];need(isinstance(v,str) and len(v)<=limit and (empty or v.strip()) and all(ord(x)>=32 for x in v),'invalid text')
        need(all(type(c[k]) is bool for k in ('enabled','visible','hide_empty')), 'invalid flags')
        need(type(c['order']) is int and 0<=c['order']<=999,'invalid order')
        for key in ('include_terms','exclude_terms'):
            need(isinstance(c[key],list) and len(c[key])<=30 and all(isinstance(v,str) and v.strip() and len(v)<=80 and all(ord(x)>=32 for x in v) for v in c[key]),'invalid keywords')
        need(cid in BUILTINS or c['include_terms'],'custom category needs keywords')
        need(isinstance(c['source_ids'],list) and len(c['source_ids'])<=100 and all(isinstance(x,str) for x in c['source_ids']) and len(set(c['source_ids']))==len(c['source_ids']) and set(c['source_ids'])<=source_ids,'invalid source bindings')
        for key in ('manual_urls','excluded_urls'):
            values=c[key];need(isinstance(values,list) and len(values)<=200 and all(isinstance(v,str) for v in values) and len(set(values))==len(values),'invalid manual list')
            for v in values:
                u=urlsplit(v);need(len(v)<=1500 and u.scheme=='https' and u.hostname and not(u.username or u.password or u.fragment),'invalid manual URL')
        need(not set(c['manual_urls']) & set(c['excluded_urls']),'conflicting manual classification')
    need(BUILTINS<=ids,'keep built-in categories; disable or hide instead of deleting')
    return rows

def collection_category_ids(meta, source, settings):
    from content_quality import classify_content
    text=' '.join(str(meta.get(k) or '') for k in ('title','description','article_excerpt')).lower()
    category=classify_content(meta.get('title',''),meta.get('description',''))[0]
    result=[]
    for c in settings.get('navigation',[]):
        if not c['enabled'] or source['id'] not in c['source_ids']: continue
        if any(t.lower() in text for t in c['exclude_terms']): continue
        if (not c['include_terms'] and c['id']==category) or any(t.lower() in text for t in c['include_terms']): result.append(c['id'])
    return result

def collection_category_match(meta, source, settings, primary_match):
    """Connections scope discovery; neither connections nor keywords approve copy."""
    if 'navigation' not in settings: return primary_match
    return primary_match and bool(collection_category_ids(meta,source,settings))
