# Script Studio

Script Studio is the editable Frida source workspace with a user-local Script Library and import, edit, validate, and explicit load workflows. Imported, user-authored, and third-party scripts are untrusted; validation never rewrites or executes source. Advisory warnings do not block saving, while loading requires explicit review, approval, and runtime safeguards. Review scripts for sensitive collection and state changes.

RC1 includes the Script Studio framework but does not bundle a reviewed core curated script pack. User-local library directories are created as needed at runtime and remain outside packaged curated assets and Git. The disabled hello example plugin contains a harmless demonstration asset and remains separate from core curated assets.
