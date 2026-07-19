"""Bounded packet-capture lifecycle with hashing and explicit evidence registration."""
from __future__ import annotations
import hashlib,os,time,uuid
from dataclasses import dataclass,replace
from pathlib import Path
from app.core.network_models import CaptureState,PacketCaptureArtifact,PacketCaptureConfig
from app.core.pentest_event import EventCategory,PentestEvent
from app.core.environment_change import EnvironmentChange

@dataclass(frozen=True,slots=True)
class CaptureResult:
    ok:bool;value:object=None;error:str|None=None;preview:tuple[str,...]=()

class PacketCaptureManager:
    MAX_DURATION=300
    def __init__(self,adb,process,session_provider=lambda:None,timeline_provider=lambda:None,evidence_provider=lambda:None,change_provider=lambda:None,clock=time.time):
        self.adb=adb;self.process=process;self.session_provider=session_provider;self.timeline_provider=timeline_provider;self.evidence_provider=evidence_provider;self.change_provider=change_provider;self.clock=clock;self.state=CaptureState.IDLE;self.active=None;self.history=[]
    def _guard(self,config,confirmed):
        session=self.session_provider()
        if not config.device_serial:return "An explicitly selected device is required."
        if not session or not session.permits("network-analysis"):return "An active authorized assessment permitting network-analysis is required."
        if session.scope.device_serial!=config.device_serial:return "The selected device does not match the active scope."
        if not confirmed:return "Explicit confirmation is required."
        if not 1<=int(config.duration)<=self.MAX_DURATION:return f"Capture duration must be between 1 and {self.MAX_DURATION} seconds."
        if config.maximum_file_size<=0:return "Maximum file size must be positive."
        return None
    def preview(self,config):
        remote=config.remote_path or f"/data/local/tmp/sus-adb-{uuid.uuid4().hex[:12]}.pcap"
        adb_path=getattr(self.adb,"adb_path",None) or "adb";size_mb=max(1,(int(config.maximum_file_size)+999_999)//1_000_000)
        argv=(adb_path,"-s",config.device_serial,"shell","tcpdump","-i",config.interface,"-s",str(config.snap_length),"-G",str(config.duration),"-W","1","-C",str(size_mb),"-w",remote)
        if config.capture_filter:argv+=tuple(config.capture_filter.split())
        return CaptureResult(True,replace(config,remote_path=remote),preview=argv)
    def inspect_availability(self,serial):return self.adb.run("shell","command","-v","tcpdump",serial=serial,timeout=10)
    def inspect_root(self,serial):return self.adb.run("shell","id","-u",serial=serial,timeout=10)
    def start(self,config,confirmed=False):
        error=self._guard(config,confirmed)
        if error:return CaptureResult(False,error=error)
        if self.state in (CaptureState.STARTING,CaptureState.CAPTURING):return CaptureResult(False,error="A capture is already active.")
        if config.local_destination and Path(config.local_destination).exists():return CaptureResult(False,error="The local destination exists; choose another path or explicitly remove it outside capture.")
        prepared=self.preview(config);config=prepared.value;self.state=CaptureState.STARTING
        started=self.process.start(prepared.preview)
        if not started.running:self.state=CaptureState.FAILED;return CaptureResult(False,error=started.error or "Capture process failed to start.")
        self.active=PacketCaptureArtifact(config.device_serial,config.target_identifier,config.remote_path,config.local_destination,start_timestamp=str(self.clock()),capture_state=CaptureState.CAPTURING);self.state=CaptureState.CAPTURING
        tracker=self.change_provider()
        if tracker:tracker.register(EnvironmentChange("network-capture","Remote packet capture temporary file",config.remote_path,config.device_serial,config.target_identifier,restoration_instructions="Remove only this SUS-ADB-created temporary capture after successful pull.",restoration_command_preview=f"adb -s {config.device_serial} shell rm {config.remote_path}"))
        self._event("Packet capture started",config.display_label);return CaptureResult(True,self.active,preview=prepared.preview)
    def stop(self):
        if not self.active:return CaptureResult(False,error="No capture is active.")
        self.state=CaptureState.STOPPING;result=self.process.stop();artifact=self.active
        if result.error:self.state=CaptureState.FAILED;return CaptureResult(False,error=result.error)
        self.state=CaptureState.PULLING
        if artifact.remote_path and artifact.local_path:
            pull=self.adb.run("pull",artifact.remote_path,artifact.local_path,serial=artifact.device_serial,timeout=60)
            if not pull.ok:self.state=CaptureState.FAILED;return CaptureResult(False,error=pull.output)
            path=Path(artifact.local_path)
            if not path.is_file():self.state=CaptureState.FAILED;return CaptureResult(False,error="Pulled capture file is missing.")
            self.state=CaptureState.HASHING;data=path.read_bytes();digest=hashlib.sha256(data).hexdigest()
            self.adb.run("shell","rm",artifact.remote_path,serial=artifact.device_serial,timeout=10)
            artifact=replace(artifact,stop_timestamp=str(self.clock()),duration=max(0,self.clock()-float(artifact.start_timestamp)),file_size=len(data),sha256=digest,capture_state=CaptureState.COMPLETED)
        elif artifact.local_path:
            path=Path(artifact.local_path)
            if not path.is_file():self.state=CaptureState.FAILED;return CaptureResult(False,error="Host capture file is missing.")
            data=path.read_bytes();artifact=replace(artifact,stop_timestamp=str(self.clock()),duration=max(0,self.clock()-float(artifact.start_timestamp)),file_size=len(data),sha256=hashlib.sha256(data).hexdigest(),capture_state=CaptureState.COMPLETED)
        else:artifact=replace(artifact,stop_timestamp=str(self.clock()),capture_state=CaptureState.COMPLETED)
        self.state=CaptureState.COMPLETED;self.active=None;self.history.append(artifact);self._event("Packet capture completed",artifact.display_label);return CaptureResult(True,artifact)
    def cancel(self):
        if not self.active:return CaptureResult(False,error="No capture is active.")
        self.process.cancel();artifact=replace(self.active,capture_state=CaptureState.CANCELLED);self.active=None;self.state=CaptureState.CANCELLED;self._event("Packet capture cancelled",artifact.remote_path);return CaptureResult(True,artifact)
    def import_pcap(self,path,device_serial="",target_identifier=""):
        p=Path(path).expanduser().resolve()
        if not p.is_file():return CaptureResult(False,error="Select an existing PCAP file.")
        data=p.read_bytes();artifact=PacketCaptureArtifact(device_serial,target_identifier,local_path=str(p),file_size=len(data),sha256=hashlib.sha256(data).hexdigest(),capture_state=CaptureState.COMPLETED);self.history.append(artifact);self._event("PCAP imported",artifact.display_label);return CaptureResult(True,artifact)
    def list_interfaces(self,serial):return self.adb.run("shell","tcpdump","-D",serial=serial,timeout=10)
    def start_host(self,config,confirmed=False,executable="tcpdump"):
        error=self._guard(config,confirmed)
        if error:return CaptureResult(False,error=error)
        if config.local_destination and Path(config.local_destination).exists():return CaptureResult(False,error="The local destination exists; choose another path.")
        argv=(executable,"-i",config.interface,"-s",str(config.snap_length),"-G",str(config.duration),"-W","1","-C",str(max(1,(config.maximum_file_size+999_999)//1_000_000)),"-w",config.local_destination)
        started=self.process.start(argv)
        if not started.running:return CaptureResult(False,error=started.error or "Host capture failed to start.")
        self.active=PacketCaptureArtifact(config.device_serial,config.target_identifier,local_path=config.local_destination,start_timestamp=str(self.clock()),capture_state=CaptureState.CAPTURING);self.state=CaptureState.CAPTURING;self._event("Host packet capture started",config.display_label);return CaptureResult(True,self.active,preview=argv)
    def add_to_evidence(self,artifact):
        session=self.session_provider();store=self.evidence_provider()
        if not session or not session.permits("evidence-collection"):return CaptureResult(False,error="Evidence-collection scope is required.")
        if not store:return CaptureResult(False,error="No active evidence store.")
        result=store.import_file(artifact.local_path,title=f"Network capture {Path(artifact.local_path).name}",description="Potentially sensitive authorized packet capture")
        return CaptureResult(result.ok,replace(artifact,evidence_id=result.item.evidence_id) if result.ok else None,result.error)
    def disconnect(self,serial):
        if self.active and self.active.device_serial==serial:return self.cancel()
        return CaptureResult(True)
    def shutdown(self):return self.cancel() if self.active else CaptureResult(True)
    def _event(self,title,description):
        timeline=self.timeline_provider()
        if timeline:timeline.append(PentestEvent(EventCategory.NETWORK,"network-workspace",title,description))
