(function() {
  var path = location.pathname;
  if (path.indexOf('/events/') === -1) return;
  var slug = path.replace(/.*\//, '').replace(/\.html$/, '');
  if (!slug) return;

  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/events.json?v=' + Date.now(), true);
  xhr.onload = function() {
    if (xhr.status !== 200) return;
    try {
      var events = JSON.parse(xhr.responseText);
      var ev = events.find(function(e) { return e.slug === slug; });
      if (!ev) return;
      if (!ev.officialUrl && !ev.officialInstagram) return;

      var container = document.createElement('div');
      container.className = 'official-links-section';
      container.style.cssText = 'margin:2rem 0;padding:1.2rem 1.5rem;background:linear-gradient(135deg,#f8fdf8,#edf7ed);border-radius:12px;border:1px solid #c8e6c9;';

      var title = document.createElement('h4');
      title.style.cssText = 'margin:0 0 0.8rem;font-size:1rem;color:#2e7d32;display:flex;align-items:center;gap:6px;';
      title.innerHTML = '\u2714 \u516c\u5f0f\u30ea\u30f3\u30af';
      container.appendChild(title);

      var linksWrap = document.createElement('div');
      linksWrap.style.cssText = 'display:flex;flex-wrap:wrap;gap:12px;';

      if (ev.officialUrl) {
        var a1 = document.createElement('a');
        a1.href = ev.officialUrl;
        a1.target = '_blank';
        a1.rel = 'noopener noreferrer';
        a1.style.cssText = 'display:inline-flex;align-items:center;gap:6px;padding:8px 16px;background:#fff;border:1px solid #a5d6a7;border-radius:8px;color:#2e7d32;text-decoration:none;font-weight:600;font-size:0.95rem;transition:all 0.2s;';
        a1.innerHTML = '\ud83d\udd17 \u516c\u5f0f\u30b5\u30a4\u30c8';
        a1.onmouseover = function(){ this.style.background='#e8f5e9'; };
        a1.onmouseout = function(){ this.style.background='#fff'; };
        linksWrap.appendChild(a1);
      }

      if (ev.officialInstagram) {
        var igUrl = ev.officialInstagram.indexOf('http') === 0 ? ev.officialInstagram : 'https://www.instagram.com/' + ev.officialInstagram.replace('@','') + '/';
        var a2 = document.createElement('a');
        a2.href = igUrl;
        a2.target = '_blank';
        a2.rel = 'noopener noreferrer';
        a2.style.cssText = 'display:inline-flex;align-items:center;gap:6px;padding:8px 16px;background:#fff;border:1px solid #e1bee7;border-radius:8px;color:#8e24aa;text-decoration:none;font-weight:600;font-size:0.95rem;transition:all 0.2s;';
        a2.innerHTML = '\ud83d\udcf7 \u516c\u5f0fInstagram';
        a2.onmouseover = function(){ this.style.background='#f3e5f5'; };
        a2.onmouseout = function(){ this.style.background='#fff'; };
        linksWrap.appendChild(a2);
      }

      container.appendChild(linksWrap);

      var reSection = document.querySelector('.re-section');
      var gcalLink = document.querySelector('a[href*="calendar.google.com"]');
      if (gcalLink && gcalLink.parentElement) {
        gcalLink.parentElement.insertAdjacentElement('afterend', container);
      } else if (reSection) {
        reSection.parentElement.insertBefore(container, reSection);
      }
    } catch(e) {}
  };
  xhr.send();
})();
