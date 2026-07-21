'use strict';
// Observation-only starter agent. It is packaged as editable, untrusted, and unloaded.
if (Java.available) {
  Java.perform(function () {
    const WebView = Java.use('android.webkit.WebView');
    Java.choose('android.webkit.WebView', {
      onMatch: function (view) {
        let url = '', title = '';
        try { url = String(view.getUrl() || '').slice(0, 240); } catch (_) {}
        try { title = String(view.getTitle() || '').slice(0, 240); } catch (_) {}
        send({type: 'webview-instance', class: String(view.getClass().getName()).slice(0, 160), url: url, title: title});
      },
      onComplete: function () { send({type: 'webview-enumeration-complete'}); }
    });
  });
} else {
  send({type: 'webview-java-unavailable'});
}
