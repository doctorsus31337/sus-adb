"""Stable local report-data assembly; evidence contents are excluded."""
from __future__ import annotations
import hashlib,json
class ReportAssembler:
    ORDER={"informational":0,"low":1,"medium":2,"high":3,"critical":4}
    def assemble(self,session,profile,findings=(),timeline=(),evidence=(),notes=(),changes=(),redactor=None,summaries=None):
        minimum=self.ORDER.get(profile.minimum_finding_severity,0);selected=sorted((f for f in findings if f.status.value in profile.included_finding_statuses and self.ORDER[f.severity.value]>=minimum),key=lambda f:(-self.ORDER[f.severity.value],f.title.casefold(),f.finding_id))
        unresolved=[c for c in changes if getattr(getattr(c,"state",None),"value","") not in {"restored","abandoned"}]
        warnings=[]
        if not session.scope.authorization_confirmed:warnings.append("Authorization is not confirmed.")
        if session.state.value not in {"active","completed"}:warnings.append(f"Assessment session state is {session.state.value}.")
        if unresolved:warnings.append(f"{len(unresolved)} unresolved environment change(s) remain.")
        data={"cover":{"organization":profile.organization,"title":profile.report_title,"subtitle":profile.report_subtitle,"author":profile.author,"reviewer":profile.reviewer,"classification":profile.classification},"authorization":{"case":session.scope.case_name,"reference":session.scope.authorization_reference,"confirmed":session.scope.authorization_confirmed,"scope_digest":session.scope.digest,"allowed":list(session.scope.allowed_actions),"excluded":list(session.scope.excluded_actions)},"executive_summary":{"finding_count":len(selected),"severity_summary":{s:sum(f.severity.value==s for f in selected) for s in self.ORDER}},"methodology":"Authorized, evidence-led application and device security assessment.","tool_versions":dict(session.tool_snapshot),"timeline":[e.to_dict() for e in sorted(timeline,key=lambda e:(e.timestamp,e.event_id))] if profile.include_timeline_summary else [],"findings":[f.to_dict() for f in selected],"evidence_manifest":[i.to_dict() for i in sorted(evidence,key=lambda i:i.evidence_id)],"notes":[n.to_dict() for n in sorted(notes,key=lambda n:n.note_id)],"unresolved_environment_changes":[c.to_dict() for c in unresolved] if profile.include_environment_changes else [],"limitations":warnings,"remediation_summary":[{"finding_id":f.finding_id,"title":f.title,"remediation":f.remediation} for f in selected],"summaries":dict(summaries or {}),"profile":profile.to_dict()}
        return redactor.apply_data(data) if redactor else data
    @staticmethod
    def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
