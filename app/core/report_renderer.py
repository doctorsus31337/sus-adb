"""Deterministic offline JSON, Markdown and safe HTML rendering."""
from __future__ import annotations
import html,json
class ReportRenderer:
    @staticmethod
    def json(data):return json.dumps(data,indent=2,sort_keys=True,default=str)+"\n"
    @staticmethod
    def markdown(data):
        cover=data["cover"];lines=[f"# {cover['title']}",cover.get("subtitle","") ,f"**Classification:** {cover.get('classification','')}","","## Executive Summary",f"Findings: {data['executive_summary']['finding_count']}","","## Findings"]
        for f in data["findings"]:lines += [f"### {f['severity'].upper()}: {f['title']}",f.get("summary","") or f.get("detailed_description",""),"",f"**Impact:** {f.get('impact','')}",f"**Remediation:** {f.get('remediation','')}",""]
        lines += ["## Evidence Integrity Manifest"]+[f"- `{e.get('sha256','')}` — {e.get('title','')}" for e in data["evidence_manifest"]]
        if data["unresolved_environment_changes"]:lines += ["","## Unresolved Environment Changes"]+[f"- {c.get('title','')}" for c in data["unresolved_environment_changes"]]
        lines += ["","## Limitations"]+[f"- {v}" for v in data["limitations"]]
        return "\n".join(lines).rstrip()+"\n"
    @staticmethod
    def html(data):
        esc=lambda v:html.escape(str(v),quote=True);cover=data["cover"];findings=[]
        for f in data["findings"]:
            anchor="finding-"+esc(f["finding_id"]);findings.append(f"<article id=\"{anchor}\"><h3>{esc(f['severity']).upper()}: {esc(f['title'])}</h3><p>{esc(f.get('detailed_description',''))}</p><h4>Impact</h4><p>{esc(f.get('impact',''))}</p><h4>Remediation</h4><p>{esc(f.get('remediation',''))}</p></article>")
        toc="".join(f"<li><a href=\"#finding-{esc(f['finding_id'])}\">{esc(f['title'])}</a></li>" for f in data["findings"]);evidence="".join(f"<tr><td>{esc(e.get('title',''))}</td><td><code>{esc(e.get('sha256',''))}</code></td></tr>" for e in data["evidence_manifest"]);warnings="".join(f"<li>{esc(v)}</li>" for v in data["limitations"])
        return "<!doctype html><html><head><meta charset=\"utf-8\"><title>"+esc(cover["title"])+"</title><style>body{font:16px sans-serif;max-width:960px;margin:auto;color:#211}h1,h2,h3{color:#710b18}table{border-collapse:collapse;width:100%}td,th{border:1px solid #777;padding:.4rem}@media print{nav{display:none}}</style></head><body><h1>"+esc(cover["title"])+"</h1><p>"+esc(cover.get("subtitle",""))+"</p><p><strong>Classification:</strong> "+esc(cover.get("classification",""))+"</p><nav><h2>Contents</h2><ol>"+toc+"</ol></nav><h2>Executive Summary</h2><p>"+str(data["executive_summary"]["finding_count"])+" finding(s).</p><h2>Detailed Findings</h2>"+"".join(findings)+"<h2>Evidence Integrity Manifest</h2><table><tr><th>Evidence</th><th>SHA-256</th></tr>"+evidence+"</table><h2>Warnings and Limitations</h2><ul>"+warnings+"</ul></body></html>"
