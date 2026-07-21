# WebView Security Inspector

Static analysis accepts only selected local inputs and reports bounded candidates, never automatic confirmed findings. The editable Frida starter agent is untrusted and unloaded by default, guards `Java.available`, truncates values, and observes metadata only. It does not capture complete page content, inject page JavaScript, modify arguments/returns or SSL decisions, bypass TLS/pinning, or load itself.
