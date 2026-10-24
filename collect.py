import os, re, json, time, hashlib, urllib.parse, urllib.request, html as H
import feedparser

MODEL = os.environ.get("MODEL", "claude-haiku-5-5")
STATES = ["Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh","Goa","Gujarat","Haryana","Himachal Pradesh","Jharkhand","Karnataka","Kerala","Madhya Pradesh","Maharashtra","Manipur","Meghalaya","Mizoram","Nagaland","Odisha","Punjab","Rajasthan","Sikkim","Tamil Nadu","Telangana","Tripura","Uttar Pradesh","Uttarakhand","West Bengal","Delhi","Jammu and Kashmir","Ladakh","Puducherry","Chandigarh"]
COUNTRIES = ["New Zealand","Australia","Singapore","Japan","South Korea","China","Israel","Netherlands","Germany","France","Italy","Spain","Switzerland","UK","United Kingdom","USA","United States","Canada","UAE","Dubai","Thailand","Malaysia","Vietnam","Sri Lanka","Bhutan","Nepal","Denmark","Sweden","Finland","Norway","Russia","Brazil","South Africa","Egypt","Taiwan","Indonesia","Philippines","Turkey","Germany"]
KW = r"delegat|study tour|exposure (visit|trip|tour)|foreign (tour|visit)|team (of|led by).{0,40}(visit|leaves|to)|sent abroad|to visit|will visit|leaves for|study visit"
FIELDS = {"Horticulture":"horticult|orchard|floricult","Agriculture":"agricult|farmer|crop|dairy|livestock","Education":"school|teacher|education|university|principal","Health":"health|hospital|doctor|medical","Sports":"sport|athlete|olympic|games|coach","IT / AI":"\\bAI\\b|artificial intelligence|information technology|software|semiconductor|startup","Tourism":"tourism|tourist","Industry / Investment":"investor|industr|investment|roadshow|summit","Urban / Infra":"urban|metro|smart city|infrastructure|waste","Fisheries":"fisher|aquacult","Skill / Youth":"skill|youth|vocational|ITI","Culture":"culture|art|craft|handloom"}
QUERIES = [f'"{s}" government delegation abroad visit' for s in STATES] + [
 "state government delegation study tour abroad", "chief minister leads delegation to visit abroad",
 "state officials exposure visit foreign country", "state government sends delegates to attend abroad training",
 "site:pib.gov.in delegation visit state", "state government team to visit abroad study"]


def rule_extract(title, text):
    blob = f"{title}. {text}"
    if not re.search(KW, blob, re.I): return None
    st = next((s for s in STATES if s.lower() in blob.lower()), None)
    co = next((x for x in COUNTRIES if re.search(r"\b"+x+r"\b", blob)), None)
    if not (st and co): return None
    fd = next((k for k, v in FIELDS.items() if re.search(v, blob, re.I)), "Other")
    m = re.search(r"(\d+|two|three|four|five|six|seven|eight|nine|ten)\s+(delegates|officials|members|farmers|teachers|MLAs|students)", blob, re.I)
    return dict(state=st, field=fd, country=co, delegates=m.group(0) if m else "", dates="", summary=title, confidence=0.5)

def ai_extract(title, text):
    import anthropic
    cl = anthropic.Anthropic()
    p = ("From this Indian news item decide if an INDIAN STATE/UT/DISTRICT GOVERNMENT is sending/sent officials, ministers or delegates to a FOREIGN country "
         "(study, training, investment, sports, culture, any field). Reply ONLY JSON: {\"is_delegation\":bool,\"state\":str,\"field\":str,\"country\":str,"
         "\"delegates\":str,\"dates\":str,\"summary\":str(max 25 words),\"confidence\":0-1}. Use empty strings if unknown; never guess.\n\n"
         f"TITLE: {title}\nTEXT: {text[:1500]}")
    r = cl.messages.create(model=MODEL, max_tokens=300, messages=[{"role":"user","content":p}])
    j = json.loads(re.search(r"\{.*\}", r.content[0].text, re.S).group(0))
    return j if j.get("is_delegation") and j.get("state") and j.get("country") else None


DEPT = {"Horticulture":"Horticulture Department","Agriculture":"Agriculture Department","Education":"Education Department","Health":"Health and Family Welfare Department","Sports":"Sports and Youth Affairs Department","IT / AI":"Information Technology Department","Tourism":"Tourism Department","Industry / Investment":"Industries and Commerce Department","Urban / Infra":"Urban Development Department","Fisheries":"Fisheries Department","Skill / Youth":"Skill Development Department","Culture":"Art and Culture Department","Other":"General Administration Department"}
CF = "docs/contacts.json"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124 Safari/537.36"}
def get(url, t=15):
    r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=t)
    return r.read(600000).decode("utf-8", "ignore")
def gov(u):
    h = urllib.parse.urlparse(u).netloc.lower()
    return h.endswith("gov.in") or h.endswith("nic.in")
def search_gov(q):
    out = []
    try: page = get("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(q))
    except Exception: return out
    for m in re.findall(r'uddg=([^&"]+)', page):
        u = urllib.parse.unquote(m)
        if gov(u) and u not in out: out.append(u)
    return out[:3]
def clean(t):
    t = H.unescape(t)
    t = re.sub(r"\s*[\[\(]\s*at\s*[\]\)]\s*", "@", t, flags=re.I)
    return re.sub(r"\s*[\[\(]\s*dot\s*[\]\)]\s*", ".", t, flags=re.I)
def extract(text):
    text = clean(re.sub(r"<[^>]+>", " ", text))
    em = [e.lower().strip(".") for e in re.findall(r"[\w.\-+]+@[\w\-]+(?:\.[\w\-]+)+", text)]
    em = list(dict.fromkeys(e for e in em if e.endswith("gov.in") or e.endswith("nic.in")))
    ph = re.findall(r"(?:\+91[\s-]?)?\(?0\d{2,4}\)?[\s-]?\d{6,8}|\+91[\s-]?\d{10}", text)
    ph = list(dict.fromkeys(re.sub(r"\s+", " ", p).strip() for p in ph))
    return em[:3], ph[:3]
def find_contact(state, field):
    d = DEPT.get(field, DEPT["Other"])
    urls = search_gov(f"{state} {d} government official contact email") or search_gov(f"{state} {d} contact us")
    emails, phones, site = [], [], ""
    for u in urls:
        try: pg = get(u)
        except Exception: continue
        site = site or u
        pages = [pg]
        for h in re.findall(r'href=["\']([^"\']*contact[^"\']*)["\']', pg, re.I)[:2]:
            try: pages.append(get(urllib.parse.urljoin(u, h)))
            except Exception: pass
        for p in pages:
            e, ph = extract(p); emails += e; phones += ph
        if emails or phones: break
    return dict(dept=d, site=site, emails=list(dict.fromkeys(emails))[:3], phones=list(dict.fromkeys(phones))[:3], checked=time.time())
def update_contacts(recs):
    try: C = json.load(open(CF))
    except Exception: C = {}
    n = 0
    for k in dict.fromkeys(f"{r['state']}|{r['field']}" for r in recs):
        if n >= 20: break
        if k in C and time.time() - C[k].get("checked", 0) < 30 * 86400: continue
        st, fd = k.split("|"); C[k] = find_contact(st, fd); n += 1; time.sleep(2)
    json.dump(C, open(CF, "w"), ensure_ascii=False)
    print("contacts looked up:", n)

OUT = "docs/data.json"
def collect():
    try: old = json.load(open(OUT))
    except Exception: old = []
    seen = {x["id"] for x in old}; ai = bool(os.environ.get("ANTHROPIC_API_KEY")); new = []
    for q in QUERIES:
        url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:7d") + "&hl=en-IN&gl=IN&ceid=IN:en"
        try: feed = feedparser.parse(url)
        except Exception: continue
        for e in feed.entries[:15]:
            title = e.get("title", ""); id_ = hashlib.sha1(re.sub(r"\W+", "", title.lower())[:80].encode()).hexdigest()
            if id_ in seen: continue
            seen.add(id_); text = re.sub("<[^>]+>", " ", e.get("summary", ""))
            try: x = ai_extract(title, text) if ai else rule_extract(title, text)
            except Exception: x = rule_extract(title, text)
            if not x or float(x.get("confidence", 0)) < 0.5: continue
            new.append(dict(id=id_, state=x["state"], field=x.get("field") or "Other", country=x["country"], delegates=x.get("delegates", ""), dates=x.get("dates", ""), summary=x.get("summary", title), title=title, url=e.get("link", ""), source=(e.get("source") or {}).get("title", "News"), published=e.get("published", ""), confidence=float(x.get("confidence", .5)), found=time.time()))
        time.sleep(1)
    json.dump(new + old, open(OUT, "w"), ensure_ascii=False)
    try: update_contacts(new + old)
    except Exception as ex: print("contact error", ex)
    print("new:", len(new))
if __name__ == "__main__": collect()
