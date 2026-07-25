"""Finding completeness and lifecycle validation."""
from dataclasses import dataclass
from app.core.security_finding import FindingStatus
@dataclass(frozen=True,slots=True)
class FindingValidation:
    errors:tuple[str,...]=();warnings:tuple[str,...]=();suggestions:tuple[str,...]=()
    @property
    def valid(self):return not self.errors
class FindingValidator:
    TRANSITIONS={FindingStatus.DRAFT:{FindingStatus.OPEN,FindingStatus.NEEDS_REVIEW},FindingStatus.OPEN:{FindingStatus.NEEDS_REVIEW,FindingStatus.ACCEPTED_RISK,FindingStatus.REMEDIATED,FindingStatus.RETEST_REQUIRED},FindingStatus.NEEDS_REVIEW:{FindingStatus.OPEN,FindingStatus.DRAFT},FindingStatus.ACCEPTED_RISK:{FindingStatus.OPEN,FindingStatus.CLOSED},FindingStatus.REMEDIATED:{FindingStatus.RETEST_REQUIRED,FindingStatus.CLOSED},FindingStatus.RETEST_REQUIRED:{FindingStatus.REMEDIATED,FindingStatus.OPEN,FindingStatus.CLOSED},FindingStatus.CLOSED:{FindingStatus.OPEN}}
    def validate(self,finding,*,evidence_ids=(),event_ids=(),authorization=False,for_review=False):
        errors=[];warnings=[];suggestions=[]
        if not finding.title.strip():errors.append("A finding title is required.")
        if not finding.detailed_description.strip():errors.append("A detailed description is required.")
        if for_review and not finding.affected_target_identifiers:errors.append("An affected target is required before review.")
        if not finding.reproduction_steps:warnings.append("Reproduction steps are incomplete.")
        if not finding.remediation.strip():warnings.append("Remediation guidance is incomplete.")
        if not authorization:warnings.append("Authorization context is missing.")
        missing_e=sorted(set(finding.evidence_ids)-set(evidence_ids));missing_t=sorted(set(finding.timeline_event_ids)-set(event_ids))
        if missing_e:warnings.append("Broken evidence references: "+", ".join(missing_e))
        if missing_t:warnings.append("Broken timeline references: "+", ".join(missing_t))
        if finding.sensitivity not in {"public","internal"} and finding.redaction_state!="reviewed":warnings.append("Sensitive content has unresolved redaction review.")
        if not finding.impact:suggestions.append("Describe business and technical impact.")
        if not finding.expected_secure_result:suggestions.append("Describe the expected secure result.")
        return FindingValidation(tuple(errors),tuple(warnings),tuple(suggestions))
    def transition(self,old,new):
        old=FindingStatus(old);new=FindingStatus(new)
        return FindingValidation() if old==new or new in self.TRANSITIONS.get(old,set()) else FindingValidation((f"Invalid lifecycle transition from {old.value} to {new.value}.",))
