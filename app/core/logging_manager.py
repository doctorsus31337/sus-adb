"""Thread-safe rotating local logs with conservative redaction."""
from __future__ import annotations
import json,logging,logging.handlers,re,threading,uuid
from pathlib import Path
class RedactionFilter(logging.Filter):
    PATTERNS=((re.compile(r"(?i)(password|token|secret|authorization)\s*[:=]\s*\S+"),r"\1=[REDACTED]"),(re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),"[PRIVATE-KEY-REDACTED]"),(re.compile(r"(?:/home/[^/\s]+|C:\\Users\\[^\\\s]+)"),"[LOCAL-HOME-REDACTED]"))
    def filter(self,record):
        text=record.getMessage()
        for pattern,replacement in self.PATTERNS:text=pattern.sub(replacement,text)
        record.msg=text;record.args=();return True
class JsonFormatter(logging.Formatter):
    def format(self,record):return json.dumps({"timestamp":self.formatTime(record),"level":record.levelname,"logger":record.name,"message":record.getMessage(),"session_id":getattr(record,"session_id","")},sort_keys=True)
class LoggingManager:
    def __init__(self,directory,level="INFO",structured=True,max_bytes=1_000_000,backups=3):
        self.directory=Path(directory).resolve();self.session_id=str(uuid.uuid4());self.lock=threading.RLock();self.logger=logging.getLogger(f"sus-adb.{id(self)}");self.logger.setLevel(getattr(logging,str(level).upper(),logging.INFO));self.logger.propagate=False
        try:
            self.directory.mkdir(parents=True,exist_ok=True);handler=logging.handlers.RotatingFileHandler(self.directory/("application.jsonl" if structured else "application.log"),maxBytes=max_bytes,backupCount=backups,encoding="utf-8");handler.addFilter(RedactionFilter());handler.setFormatter(JsonFormatter() if structured else logging.Formatter("%(asctime)s %(levelname)s %(message)s"));self.logger.addHandler(handler)
        except OSError: self.logger.addHandler(logging.NullHandler())
    def log(self,level,message,**context):
        try:
            with self.lock:self.logger.log(getattr(logging,str(level).upper(),logging.INFO),str(message),extra={"session_id":self.session_id,**context})
        except Exception:pass
    def exception(self,message):
        try:self.logger.exception(message,extra={"session_id":self.session_id})
        except Exception:pass
    def tail(self,limit=50):
        try:path=next(iter(self.directory.glob("application.*")));return tuple(path.read_text(encoding="utf-8",errors="replace").splitlines()[-limit:])
        except (OSError,StopIteration):return ()
    def export(self,path):Path(path).write_text("\n".join(self.tail(1000))+"\n",encoding="utf-8")
    def close(self):
        for h in tuple(self.logger.handlers):
            try:h.flush();h.close()
            except Exception:pass
            self.logger.removeHandler(h)
