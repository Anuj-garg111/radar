import os, re, json, time, hashlib, urllib.parse, urllib.request, html as H
from datetime import date, timedelta
import feedparser

MODEL = os.environ.get("MODEL", "claude-haiku-5-5")
STATES = ["Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh","Goa","Gujarat","Haryana","Himachal Pradesh","Jharkhand","Karnataka","Kerala","Madhya Pradesh","Maharashtra","Manipur","Meghalaya","Mizoram","Nagaland","Odisha","Punjab","Rajasthan","Sikkim","Tamil Nadu","Telangana","Tripura","Uttar Pradesh","Uttarakhand","West Bengal","Delhi","Jammu and Kashmir","Ladakh","Puducherry","Chandigarh"]
COUNTRIES = ["New Zealand","Australia","Singapore","Japan","South Korea","China","Israel","Netherlands","Germany","France","Italy","Spain","Switzerland","UK","United Kingdom","USA","United States","Canada","UAE","Dubai","Thailand","Malaysia","Vietnam","Sri Lanka","Bhutan","Nepal","Denmark","Sweden","Finland","Norway","Russia","Brazil","South Africa","Egypt","Taiwan","Indonesia","Philippines","Turkey","Germany"]
KW = r"delegat|study tour|exposure (visit|trip|tour)|foreign (tour|visit)|team (of|led by).{0,40}(visit|leaves|to)|sent abroad|to visit|will visit|leaves for|study visit"
FIELDS = {"Horticulture":"horticult|orchard|floricult","Agriculture":"agricult|farmer|crop|dairy|livestock","Education":"school|teacher|education|university|principal","Health":"health|hospital|doctor|medical","Sports":"sport|athlete|olympic|games|coach","IT / AI":"\\bAI\\b|artificial intelligence|information technology|software|semiconductor|startup","Tourism":"tourism|tourist","Industry / Investment":"investor|industr|investment|roadshow|summit","Urban / Infra":"urban|metro|smart city|infrastructure|waste","Fisheries":"fisher|aquacult","Skill / Youth":"skill|youth|vocational|ITI","Culture":"culture|art|craft|handloom"}
TOP = ["New Zealand","Australia","Singapore","Japan","South Korea","China","Israel","Netherlands","Germany","France","Italy","Spain","Switzerland","United Kingdom","United States","Canada","UAE","Thailand","Malaysia","Vietnam","Denmark","Sweden","Finland","Russia","Brazil","South Africa","Taiwan"]
QUERIES = ([f'"{s}" government delegation abroad' for s in STATES] + [f'"{s}" officials foreign visit study tour' for s in STATES] + [f'"{s}" minister to visit abroad' for s in STATES]
 + [f"Indian state government delegation to {c}" for c in TOP] + [f"state officials exposure visit {c}" for c in TOP]
 + ["state government delegation study tour abroad", "chief minister leads delegation to visit abroad", "state government sends delegates abroad training",
    "state sports team officials abroad government sponsored", "site:pib.gov.in delegation visit state"])


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
         "(study, training, investment, sports, culture, any field). Today is " + date.today().isoformat() + ". Reply ONLY JSON: {\"is_delegation\":bool,\"state\":str,\"field\":str,\"country\":str,"
         "\"delegates\":str,\"dates\":str,\"start_date\":\"YYYY-MM-DD or empty\",\"end_date\":\"YYYY-MM-DD or empty\",\"status\":\"upcoming|ongoing|past|unclear\",\"summary\":str(max 25 words),\"confidence\":0-1}. Use empty strings if unknown; never guess.\n\n"
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

MN = {"january":1,"february":2,"march":3,"april":4,"may":5,"june":6,"july":7,"august":8,"september":9,"october":10,"november":11,"december":12,"jan":1,"feb":2,"mar":3,"apr":4,"jun":6,"jul":7,"aug":8,"sep":9,"sept":9,"oct":10,"nov":11,"dec":12}
DRX = re.compile(r"(?:(\d{1,2})(?:st|nd|rd|th)?(?:\s*(?:-|–|to)\s*(\d{1,2})(?:st|nd|rd|th)?)?\s+(?:of\s+)?)?\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)\b\.?(?:\s+(\d{1,2})(?:st|nd|rd|th)?\b(?!\s*(?:delegates|officials|members)))?(?:,?\s+(20\d\d))?", re.I)
PAST = re.compile(r"\b(returned|visited|concluded|completed|attended|toured|came back|wrapped up|were in|was in|got back)\b", re.I)
FUT = re.compile(r"\b(will|to visit|set to|scheduled|leaves|leaving|proposes?|plans?|planning|upcoming|next (?:week|month)|to leave|to travel|to attend|embark|slated|to tour|to lead|to study)\b", re.I)
def parse_dates(t, today):
    out = []
    for m in DRX.finditer(t):
        d1, d2, mon, d3, yr = m.groups(); k = mon.lower()
        if not (d1 or d3 or yr) and (k == "may" or len(k) <= 4 and k not in ("june","july")): continue
        mo = MN[k]; y = int(yr) if yr else today.year
        try:
            if d1 or d3:
                s0 = date(y, mo, int(d1 or d3)); e0 = date(y, mo, int(d2)) if d2 else s0
            else:
                s0 = date(y, mo, 1); e0 = (date(y + (mo == 12), mo % 12 + 1, 1) - timedelta(days=1))
            if not yr and e0 < today - timedelta(days=45):
                s0 = s0.replace(year=y + 1); e0 = e0.replace(year=e0.year + 1)
            if s0 <= e0: out.append((s0, e0))
        except ValueError: pass
    return out
def evaluate(blob, start="", end=""):
    today = date.today(); s = e = None
    try:
        if start: s = date.fromisoformat(start); e = date.fromisoformat(end) if end else s
    except ValueError: s = e = None
    if not s:
        sp = parse_dates(blob, today)
        if sp: s = min(a for a, b in sp); e = max(b for a, b in sp)
    past, fut = bool(PAST.search(blob)), bool(FUT.search(blob))
    if past and not fut: st = "past"
    elif s: st = "past" if e < today else ("ongoing" if s <= today <= e else "upcoming")
    else: st = "upcoming" if fut else "unclear"
    return dict(start=s.isoformat() if s else "", end=e.isoformat() if e else "", status=st)
def load_manual():
    try: M = json.load(open("docs/manual.json"))
    except Exception: return []
    rows = []
    for m in M:
        r = dict(state=m["state"], field=m.get("field", "Other"), country=m["country"], delegates=m.get("delegates", ""), dates=m.get("dates", ""), summary=m.get("summary", ""), title=m.get("summary", ""), url=m.get("url", ""), source=m.get("source", "Manual entry"), published="", confidence=1.0, found=time.time(), manual=True)
        r["id"] = "manual-" + hashlib.sha1((r["state"] + r["country"] + r["field"] + m.get("start", "")).encode()).hexdigest()[:12]
        r.update(evaluate(r["summary"] + " " + r["dates"], m.get("start", ""), m.get("end", ""))); rows.append(r)
    return rows

OUT = "docs/data.json"
def collect():
    try: old = json.load(open(OUT))
    except Exception: old = []
    seen = {x["id"] for x in old}; ai = bool(os.environ.get("ANTHROPIC_API_KEY")); new = []
    for q in QUERIES:
        url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:60d") + "&hl=en-IN&gl=IN&ceid=IN:en"
        try: feed = feedparser.parse(url)
        except Exception: continue
        for e in feed.entries[:15]:
            title = e.get("title", ""); id_ = hashlib.sha1(re.sub(r"\W+", "", title.lower())[:80].encode()).hexdigest()
            if id_ in seen: continue
            seen.add(id_); text = re.sub("<[^>]+>", " ", e.get("summary", ""))
            try: x = ai_extract(title, text) if ai else rule_extract(title, text)
            except Exception: x = rule_extract(title, text)
            if not x or float(x.get("confidence", 0)) < 0.5: continue
            row = dict(id=id_, state=x["state"], field=x.get("field") or "Other", country=x["country"], delegates=x.get("delegates", ""), dates=x.get("dates", ""), summary=x.get("summary", title), title=title, url=e.get("link", ""), source=(e.get("source") or {}).get("title", "News"), published=e.get("published", ""), confidence=float(x.get("confidence", .5)), found=time.time())
            ev = evaluate(title + ". " + text + " " + str(x.get("dates", "")), str(x.get("start_date") or ""), str(x.get("end_date") or ""))
            if not ev["start"] and x.get("status") in ("upcoming", "ongoing", "past"): ev["status"] = x["status"]
            row.update(ev); new.append(row)
        time.sleep(1)
    man = load_manual(); mids = {m["id"] for m in man}
    for r in old:
        if r["id"] in mids or r.get("manual"): continue
        if r.get("start"): r.update(evaluate("", r["start"], r.get("end", "")))
        else:
            r.update(evaluate(r.get("title", "") + ". " + r.get("summary", "") + " " + r.get("dates", "")))
            if r["status"] in ("upcoming", "unclear") and time.time() - r.get("found", 0) > 45 * 86400: r["status"] = "past"
    allr = man + new + [r for r in old if r["id"] not in mids and not r.get("manual")]
    json.dump(allr, open(OUT, "w"), ensure_ascii=False)
    try: update_contacts([r for r in allr if r.get("status") != "past"])
    except Exception as ex: print("contact error", ex)
    print("new:", len(new))
if __name__ == "__main__": collect()
