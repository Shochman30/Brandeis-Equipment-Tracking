// Gives index.html the window.claude calls it was written for (shared saving,
// who is signed in, downloads), backed by server/app.py instead of claude.ai.
(function () {
  'use strict';
  var boot = window.__TRK || {version: 0, user: null};
  var version = boot.version, me = boot.user;

  function fail(code) { var e = new Error(code); e.code = code; return e; }

  var artifact = {
    // The page sends its whole rebuilt document; the server keeps the data in it.
    publish: function (html) {
      return fetch('api/publish', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Content-Type': 'text/html; charset=utf-8', 'X-Tracker-Version': String(version)},
        body: html
      }).then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (j) {
          if (r.ok) { version = j.version; return; }
          if (r.status === 409) {
            // Someone else saved first: show their version, as the page's message says.
            setTimeout(function () { location.reload(); }, 2500);
            throw fail('conflict');
          }
          if (r.status === 401 || r.status === 403) throw fail(j.code === 'not_writer' ? 'not_writer' : 'not_granted');
          throw fail(j.code || 'error');
        });
      });
    }
  };

  var user = {
    me: function () { return Promise.resolve(me && {id: me.id, name: me.name, isOwner: !!me.isOwner}); },
    profiles: function (ids) {
      var q = ids.map(function (i) { return 'id=' + encodeURIComponent(i); }).join('&');
      return fetch('api/profiles?' + q, {credentials: 'same-origin'}).then(function (r) { return r.ok ? r.json() : {}; });
    }
  };

  var downloads = {
    save: function (o) {
      var u = URL.createObjectURL(o.data), a = document.createElement('a');
      a.href = u; a.download = o.filename; document.body.appendChild(a); a.click();
      setTimeout(function () { URL.revokeObjectURL(u); a.remove(); }, 1500);
      return Promise.resolve({status: 'saved'});
    }
  };

  window.claude = {
    use: function (name) {
      if (name === 'artifact') return Promise.resolve(me && me.canEdit ? artifact : null);
      if (name === 'user') return Promise.resolve(user);
      if (name === 'downloads') return Promise.resolve(downloads);
      return Promise.resolve(null);
    }
  };
})();
