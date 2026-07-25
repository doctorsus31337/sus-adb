"""Transparent deterministic risk scoring (not an authoritative standard)."""
from dataclasses import dataclass,field
from typing import Mapping
from app.core.security_finding import Severity

@dataclass(frozen=True,slots=True)
class RiskScore:
    method:str;calculated_score:float|None;calculated_severity:Severity|None;final_severity:Severity;inputs:Mapping[str,object]=field(default_factory=dict);justification:str="";warnings:tuple[str,...]=()
class RiskScoring:
    LEVELS={"low":1,"medium":2,"high":3,"critical":4}; MATRIX=(("low","low","medium","medium"),("low","medium","medium","high"),("medium","medium","high","critical"),("medium","high","critical","critical"))
    @classmethod
    def manual(cls,severity,justification=""):return RiskScore("manual",None,None,Severity(severity),{"severity":Severity(severity).value},justification)
    @classmethod
    def matrix(cls,likelihood,impact,final_severity=None,justification=""):
        if likelihood not in cls.LEVELS or impact not in cls.LEVELS:raise ValueError("Likelihood and impact must be low, medium, high, or critical.")
        score=float(cls.LEVELS[likelihood]*cls.LEVELS[impact]);calculated=Severity(cls.MATRIX[cls.LEVELS[likelihood]-1][cls.LEVELS[impact]-1]);final=Severity(final_severity) if final_severity else calculated
        return RiskScore("likelihood-impact",score,calculated,final,{"likelihood":likelihood,"impact":impact},justification)
    @staticmethod
    def custom(rating,final_severity,inputs=None,justification=""):
        if not str(rating).strip():raise ValueError("A custom organization rating is required.")
        return RiskScore("custom",None,None,Severity(final_severity),{"rating":str(rating),**dict(inputs or {})},justification)
