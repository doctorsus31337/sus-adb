"""Selected-device screenshot and bounded recording service."""
from __future__ import annotations
import hashlib,subprocess,time
from pathlib import Path
from app.core.adb_explorer_models import CaptureArtifact,CaptureType
from app.core.adb_package_service import ExplorerResult

class ADBCaptureService:
    def __init__(self,adb,process_factory=None,max_duration=180,evidence_provider=lambda:None,session_provider=lambda:None):self.adb=adb;self.process_factory=process_factory or self._popen;self.max_duration=max_duration;self.evidence_provider=evidence_provider;self.session_provider=session_provider;self.process=None;self.recording=False;self.serial=""
    @staticmethod
    def _popen(argv):return subprocess.Popen(argv,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    @staticmethod
    def _digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    def screenshot(self,serial,destination,target="",add_evidence=False,confirmed=False):
        if not serial:return ExplorerResult(False,error="No device is selected.")
        session=self.session_provider()
        if not session or not session.permits("evidence-collection"):return ExplorerResult(False,error="Active scope does not permit evidence-collection.")
        if not confirmed:return ExplorerResult(False,error="Explicit capture confirmation is required.")
        dest=Path(destination).expanduser().resolve();remote=f"/data/local/tmp/sus-adb-{int(time.time())}.png"
        cap=self.adb.run("shell","screencap","-p",remote,serial=serial)
        if not cap.ok:return ExplorerResult(False,result=cap,error=cap.output)
        pull=self.adb.run("pull",remote,str(dest),serial=serial)
        if pull.ok:self.adb.run("shell","rm","--",remote,serial=serial)
        if not pull.ok or not dest.is_file():return ExplorerResult(False,result=pull,error=pull.output or "Screenshot was not pulled.")
        artifact=CaptureArtifact(CaptureType.SCREENSHOT,str(dest),remote,sha256=self._digest(dest),serial=serial,target_identifier=target);self._evidence(artifact,add_evidence);return ExplorerResult(True,artifact,pull)
    def start_recording(self,serial,destination,duration=15,target="",confirmed=False):
        if not serial:return ExplorerResult(False,error="No device is selected.")
        session=self.session_provider()
        if not session or not session.permits("evidence-collection"):return ExplorerResult(False,error="Active scope does not permit evidence-collection.")
        if not confirmed:return ExplorerResult(False,error="Explicit recording confirmation is required.")
        try:duration=int(duration)
        except ValueError:return ExplorerResult(False,error="Recording duration must be an integer.")
        if duration<1 or duration>self.max_duration:return ExplorerResult(False,error=f"Duration must be between 1 and {self.max_duration} seconds.")
        if not self.process_factory:return ExplorerResult(False,error="Screen recording process support is unavailable.")
        remote=f"/data/local/tmp/sus-adb-record-{int(time.time())}.mp4";argv=(self.adb.adb_path or "adb","-s",serial,"shell","screenrecord","--time-limit",str(duration),remote)
        try:self.process=self.process_factory(argv);self.recording=True;self.serial=serial;return ExplorerResult(True,{"destination":str(Path(destination).resolve()),"remote":remote,"duration":duration,"target":target},preview=argv)
        except Exception as exc:return ExplorerResult(False,error=f"Unable to start screenrecord: {exc}",preview=argv)
    def finish_recording(self,context,add_evidence=False):
        if self.process:
            try:self.process.wait(timeout=context["duration"]+5)
            except Exception:return ExplorerResult(False,error="screenrecord did not finish cleanly.")
        self.recording=False;dest=Path(context["destination"]);pull=self.adb.run("pull",context["remote"],str(dest),serial=self.serial)
        if pull.ok:self.adb.run("shell","rm","--",context["remote"],serial=self.serial)
        if not pull.ok or not dest.is_file():return ExplorerResult(False,result=pull,error=pull.output or "Recording was not pulled.")
        artifact=CaptureArtifact(CaptureType.SCREEN_RECORDING,str(dest),context["remote"],duration=context["duration"],sha256=self._digest(dest),serial=self.serial,target_identifier=context["target"]);self._evidence(artifact,add_evidence);return ExplorerResult(True,artifact,pull)
    def stop_recording(self):
        if self.process:
            try:self.process.terminate();self.process.wait(timeout=2)
            except Exception:
                try:self.process.kill()
                except Exception:pass
        self.recording=False;self.process=None
    def cleanup(self):self.stop_recording()
    def _evidence(self,artifact,enabled):
        if enabled:
            store=self.evidence_provider()
            if store:store.import_file(artifact.local_path,device_serial=artifact.serial,target_identifier=artifact.target_identifier)
