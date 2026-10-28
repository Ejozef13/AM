"use strict";
// Small local editor enhancement: no CDN, eval, or HTML insertion.
const codeEditor = (() => {
  const source = document.getElementById('source');
  const shell = document.createElement('div'); shell.className = 'code-editor';
  source.before(shell);
  const gutter = document.createElement('pre'); gutter.className = 'line-numbers'; gutter.setAttribute('aria-hidden','true');
  const area = document.createElement('div'); area.className = 'code-area';
  const highlight = document.createElement('pre'); highlight.className = 'code-highlight'; highlight.setAttribute('aria-hidden','true');
  shell.append(gutter,area); area.append(highlight,source); source.wrap = 'off';
  const words = new Set(('def return if else elif for while in not and or True False None class public private static int long double bool boolean void const struct typedef sizeof new delete null nullptr true false import from include using namespace std auto break continue switch case try except throw throws String ListNode TreeNode Graph').split(' '));
  function sync() {
    const text = source.value;
    highlight.replaceChildren();
    const tokens = text.match(/\/\*[\s\S]*?\*\/|\/\/[^\n]*|#[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b\d+(?:\.\d+)?\b|\b[A-Za-z_]\w*\b|[^\w'"#\/]+|./g) || [];
    for (const token of tokens) {
      const span = document.createElement('span'); span.textContent = token;
      if (/^(\/\/|\/\*|#)/.test(token)) span.className = 'token-comment';
      else if (/^["']/.test(token)) span.className = 'token-string';
      else if (/^\d/.test(token)) span.className = 'token-number';
      else if (words.has(token)) span.className = 'token-keyword';
      highlight.append(span);
    }
    highlight.append(document.createTextNode('\n'));
    gutter.textContent = Array.from({length:text.split('\n').length},(_,i)=>String(i+1)).join('\n');
    scroll();
  }
  function scroll() { highlight.scrollTop=source.scrollTop; highlight.scrollLeft=source.scrollLeft; gutter.scrollTop=source.scrollTop; }
  source.addEventListener('input',sync); source.addEventListener('scroll',scroll);
  source.addEventListener('keydown',event=>{
    if(event.key !== 'Enter' || event.ctrlKey || event.metaKey || source.readOnly) return;
    event.preventDefault();
    const line=source.value.slice(0,source.selectionStart).split('\n').pop();
    const indent=(line.match(/^\s*/)||[''])[0]+(/[{:][ \t]*$/.test(line)?'    ':'');
    source.setRangeText('\n'+indent,source.selectionStart,source.selectionEnd,'end');
    source.dispatchEvent(new Event('input'));
  });
  sync(); return {sync};
})();
