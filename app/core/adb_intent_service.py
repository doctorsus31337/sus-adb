"""Structured Android intent command construction and guarded execution."""
from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urlparse
from app.core.adb_package_service import ExplorerResult
from app.core.pentest_event import EventCategory,PentestEvent

@dataclass(frozen=True,slots=True)
class IntentExtra:
    kind:str;key:str;value:object

class ADBIntentService:
    OPERATIONS={"activity":("am","start"),"component":("am","start"),"deep-link":("am","start"),"broadcast":("am","broadcast"),"start-service":("am","startservice"),"stop-service":("am","stopservice")}
    EXTRA_FLAGS={"string":"--es","boolean":"--ez","integer":"--ei","long":"--el","float":"--ef","uri":"--eu"}
    def __init__(self,adb,session_provider=lambda:None,timeline_provider=lambda:None):self.adb=adb;self.session_provider=session_provider;self.timeline_provider=timeline_provider
    def build(self,serial,operation,package="",component="",action="",uri="",mime="",categories=(),flags=(),extras=()):
        if not serial:return ExplorerResult(False,error="No device is selected.")
        if operation not in self.OPERATIONS:return ExplorerResult(False,error="Unsupported intent operation.")
        if component and "/" not in component:return ExplorerResult(False,error="Component must use package/class syntax.")
        if uri and not urlparse(uri).scheme:return ExplorerResult(False,error="Data URI requires a scheme.")
        argv=[self.adb.adb_path or "adb","-s",serial,"shell",*self.OPERATIONS[operation]]
        if package:argv.extend(("-p",package))
        if component:argv.extend(("-n",component))
        if action:argv.extend(("-a",action))
        if uri:argv.extend(("-d",uri))
        if mime:argv.extend(("-t",mime))
        for value in categories:argv.extend(("-c",str(value)))
        for value in flags:argv.extend(("-f",str(value)))
        for extra in extras:
            try:flag=self.EXTRA_FLAGS[extra.kind]
            except KeyError:return ExplorerResult(False,error=f"Unsupported extra type: {extra.kind}")
            value=str(extra.value).lower() if isinstance(extra.value,bool) else str(extra.value);argv.extend((flag,extra.key,value))
        return ExplorerResult(True,tuple(argv),preview=tuple(argv))
    def execute(self,*args,confirmed=False,**kwargs):
        built=self.build(*args,**kwargs)
        if not built.ok:return built
        session=self.session_provider()
        if not session or not (session.permits("runtime-inspection") or session.permits("state-changing-testing")):return ExplorerResult(False,error="Active scope must permit runtime-inspection or state-changing-testing.",preview=built.preview)
        if not confirmed:return ExplorerResult(False,error="Explicit launch confirmation is required.",preview=built.preview)
        serial=args[0] if args else kwargs.get("serial");result=self.adb.run(*built.preview[3:],serial=serial)
        timeline=self.timeline_provider()
        if timeline:timeline.append(PentestEvent(EventCategory.COMMAND,"adb-explorer","Intent executed",result.output,payload={"argv":built.preview,"confirmed":True}))
        return ExplorerResult(result.ok,result.stdout,result,result.output if not result.ok else None,built.preview)
