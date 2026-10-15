"""arXiv metadata (authors, year, venue) from the public arXiv API, best effort: no key, short timeout, never stops a run.

Used for the title-page citation and the caption citation ("Smith et al., 2024") so no paper's authors are typed into the code.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import httpx

NS = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
VENUE_RE = re.compile(r"\b(ICLR|ICML|NeurIPS|NIPS|ACL|EMNLP|NAACL|EACL|COLING|CVPR|ICCV|ECCV|AAAI|IJCAI|KDD|WWW|SIGIR|UIST|CHI|CoRL|COLM|TMLR|JMLR)\b[\s\-']*((?:19|20)\d{2}|\d{2})?", re.I)


def parse(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    e = root.find("a:entry", NS)
    if e is None:
        return {}
    authors = [(n.text or "").strip() for n in e.findall("a:author/a:name", NS) if (n.text or "").strip()]
    pub = (e.findtext("a:published", default="", namespaces=NS) or "")[:4]
    comment = e.findtext("x:comment", default="", namespaces=NS) or ""
    jref = e.findtext("x:journal_ref", default="", namespaces=NS) or ""
    venue = ""
    for text in (jref, comment):
        m = VENUE_RE.search(text)
        if m:
            yr = m.group(2) or ""
            yr = ("20" + yr) if len(yr) == 2 else yr
            venue = f"{m.group(1).upper() if len(m.group(1)) <= 5 else m.group(1)} {yr}".strip()
            break
    return {"authors": authors, "year": int(pub) if pub.isdigit() else None, "venue": venue,
            "title": re.sub(r"\s+", " ", e.findtext("a:title", default="", namespaces=NS) or "").strip()}


def fetch(arxiv_id: str, timeout: float = 15.0) -> dict:
    try:
        r = httpx.get("https://export.arxiv.org/api/query", params={"id_list": arxiv_id}, timeout=timeout, headers={"User-Agent": "papertrail/0.1"})
        r.raise_for_status()
        return parse(r.text)
    except Exception:
        return {}
