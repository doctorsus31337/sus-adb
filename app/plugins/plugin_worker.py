"""Optional JSON worker adapter. This is crash containment, not a hardened sandbox."""
from __future__ import annotations
import json,os
from dataclasses import dataclass
@dataclass(frozen=True,slots=True)
class WorkerResult:
    ok:bool;response:object=None;stdout:str="";stderr:str="";error:str|None=None;cancelled:bool=False
class PluginWorker:
    def __init__(self,process_factory=None,timeout=10):self.process_factory=process_factory;self.timeout=timeout;self.process=None;self.cancelled=False
    @staticmethod
    def sanitized_environment(source=None):
        source=dict(source or os.environ);allowed=("PATH","SYSTEMROOT","WINDIR","LANG","LC_ALL","TMP","TEMP");return {k:source[k] for k in allowed if k in source}
    def request(self,argv,message,working_directory):
        if not self.process_factory:return WorkerResult(False,error="No isolated worker process adapter is configured.")
        self.cancelled=False
        try:
            self.process=self.process_factory(tuple(argv),cwd=str(working_directory),env=self.sanitized_environment(),shell=False);stdout,stderr=self.process.communicate(json.dumps(message)+"\n",timeout=self.timeout)
            if self.cancelled:return WorkerResult(False,stdout=stdout,stderr=stderr,error="Worker cancelled.",cancelled=True)
            if self.process.returncode:return WorkerResult(False,stdout=stdout,stderr=stderr,error=f"Worker exited with code {self.process.returncode}.")
            return WorkerResult(True,json.loads(stdout),stdout,stderr)
        except TimeoutError:
            self.cancel();return WorkerResult(False,error="Plugin worker timed out.",cancelled=True)
        except Exception as exc:return WorkerResult(False,error=str(exc))
        finally:self.process=None
    def cancel(self):
        self.cancelled=True
        if self.process:
            try:self.process.terminate();self.process.wait(timeout=1)
            except Exception:
                try:self.process.kill()
                except Exception:pass
    def cleanup(self):self.cancel()
