"""Synthetic/local WebView candidate analysis and structured event parsing."""
from __future__ import annotations
import json,re
from dataclasses import asdict,dataclass
from pathlib import Path
from app.plugins.contribution_registry import Contribution
from app.plugins.plugin_ui import PluginPanelSpec,PluginView

RULES=(("webview-usage",r"\bWebView\b"),("javascript-enabled",r"setJavaScriptEnabled\s*\(\s*true"),("javascript-bridge",r"addJavascriptInterface\s*\([^,]+,\s*[\"']([^\"']+)"),("file-access",r"setAllowFileAccess\s*\(\s*true"),("content-access",r"setAllowContentAccess\s*\(\s*true"),("file-url-access",r"setAllowFileAccessFromFileURLs\s*\(\s*true"),("universal-file-url-access",r"setAllowUniversalAccessFromFileURLs\s*\(\s*true"),("mixed-content",r"setMixedContentMode"),("debugging",r"setWebContentsDebuggingEnabled\s*\(\s*true"),("webview-client",r"WebViewClient"),("webchrome-client",r"WebChromeClient"),("override-url",r"shouldOverrideUrlLoading"),("intercept-request",r"shouldInterceptRequest"),("ssl-error",r"onReceivedSslError"),("ssl-continue-candidate",r"\.proceed\s*\("),("load-url",r"loadUrl\s*\("),("load-data",r"loadData(?:WithBaseURL)?\s*\("),("evaluate-javascript",r"evaluateJavascript\s*\("),("javascript-url",r"javascript:"),("cleartext",r"usesCleartextTraffic\s*=\s*[\"']true"),("network-security-config",r"networkSecurityConfig"),("custom-scheme",r"[a-z][a-z0-9+.-]+://"))
@dataclass(frozen=True,slots=True)
class Candidate:rule:str;path:str;line:int;excerpt:str;confidence:str="candidate"
@dataclass(frozen=True,slots=True)
class RuntimeEvent:event_type:str;class_name:str="";url:str="";title:str="";metadata:tuple[tuple[str,str],...]=()
def scan_text(text,path="selected-input",max_matches=500):
    values=[]
    for number,line in enumerate(text.splitlines(),1):
        for name,pattern in RULES:
            if re.search(pattern,line,re.I):values.append(Candidate(name,path,number,line.strip()[:240]));
            if len(values)>=max_matches:return tuple(values)
    return tuple(values)
def scan_files(paths,max_bytes=2*1024*1024):
    values=[]
    for raw in paths:
        p=Path(raw).resolve();data=p.read_bytes()
        if len(data)>max_bytes:raise ValueError("Selected source exceeds the bounded analysis limit.")
        values.extend(scan_text(data.decode("utf-8","replace"),p.name))
    return tuple(values)
def runtime_event(message):
    payload=message.get("payload",message) if isinstance(message,dict) else {}
    safe=lambda value:str(value or "")[:240]
    metadata=tuple(sorted((safe(k),safe(v)) for k,v in payload.items() if k not in {"type","class","url","title"}))
    return RuntimeEvent(safe(payload.get("type","observation")),safe(payload.get("class")),safe(payload.get("url")),safe(payload.get("title")),metadata)
FINDING_TEMPLATES=("Unsafe JavaScript bridge exposure","Universal file-URL access","Unsafe SSL-error handling","Mixed-content exposure","WebView debugging enabled in production","Unsafe custom-scheme validation","Unsafe external URL handling","Local-file origin confusion","Cleartext WebView traffic")
def export_json(candidates,events=()):return json.dumps({"candidates":[asdict(v) for v in candidates],"runtime_events":[asdict(v) for v in events]},indent=2,sort_keys=True)+"\n"
def export_markdown(candidates,events=()):return "# WebView Assessment\n\nStatic matches are candidates, not confirmed findings.\n\n"+"\n".join(f"- {v.rule} · {v.path}:{v.line} · confidence: {v.confidence}" for v in candidates)+"\n\n## Runtime observations\n\n"+"\n".join(f"- {v.event_type} · {v.class_name} · {v.url}" for v in events)+"\n"
def report_section(_context=None):return {"title":"WebView Assessment","body":"Candidate-only static results and observation-only runtime metadata."}
def panel_spec(_context=None):
    names=("Overview","Static Analysis","Runtime Instances","Bridges","Navigation","TLS & Content","Findings")
    return PluginPanelSpec("WebView Security Inspector",tuple(PluginView(n,"No APK/source input or runtime event is selected.",warning="Candidates require operator validation; no finding is confirmed automatically.") for n in names),{"Selected target":"None","Agent":"Untrusted and unloaded","Candidates":"0","Events":"0"})
class Plugin:
    def activate(self,api):self.api=api;return (Contribution("webview.dashboard","dashboard-card","WebView Security Inspector",factory=panel_spec),Contribution("webview.panel","pentest-panel","WebView Security Inspector",factory=panel_spec),Contribution("webview.menu","menu-action","Open WebView Inspector",metadata={"target":"webview.panel"}),Contribution("webview.agent","script-asset","WebView Observation Agent",metadata={"path":"assets/webview_observer.js"}),Contribution("webview.findings","finding-template","WebView Finding Templates",metadata={"templates":FINDING_TEMPLATES}),Contribution("webview.report","report-section","WebView Assessment",factory=report_section,capability_requirement="contribute-report-section"))
    def deactivate(self):self.api=None
