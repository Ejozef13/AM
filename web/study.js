"use strict";
async function refreshDashboard() {
  try {
    const response=await fetch('/api/dashboard');
    if(!response.ok) throw new Error('Could not load saved progress.');
    const data=await response.json();
    $('study-dashboard').hidden=!$('workspace').hidden || !$('session-summary').hidden;
    $('study-stats').textContent=`${data.today_completed || 0}/${data.goal || 1} today · ${data.streak || 0} day streak · ${data.total_completed || 0} exercises completed`;
    $('daily-goal').value=data.goal || 1;
    for(const id of ['saved-sessions','review-queue','learning-paths','practice-history']) $(id).replaceChildren();
    for(const item of data.history || []) {
      addText($('practice-history'),'p',`${item.language} · ${item.topic} · ${item.passed}/${item.total} tests · ${item.attempts} attempt(s)`,'muted');
    }
    if(!(data.history||[]).length) addText($('practice-history'),'p','Your practice history will appear here.','muted');
    const chooseTopic=(topic,language)=>{
      $('topic').value=topic;
      if(language) document.querySelector(`.language[data-language="${language}"]`)?.click();
      screen('setup'); $('setup').scrollIntoView({behavior:'smooth'});
    };
    for(const saved of data.active || []) {
      const button=addText($('saved-sessions'),'button',`Resume ${saved.language}: ${saved.title} (${saved.number}/${saved.total})`,'secondary');
      button.type='button'; button.addEventListener('click',()=>perform('Loading saved draft…',async()=>{
        try { await saveDraft(); }
        catch(error) { if(!confirm('Your current changes could not be saved. Replace them with the saved server version? Copy your code first if needed.')) throw error; }
        renderSession(await post('/api/session/resume',{session_id:saved.session_id}));
      }));
    }
    if(!(data.active||[]).length) addText($('saved-sessions'),'p','No unfinished sessions yet.','muted');
    for(const review of data.due || []) {
      const button=addText($('review-queue'),'button',`${review.language}: ${review.topic}`,'secondary');
      button.type='button'; button.addEventListener('click',()=>chooseTopic(review.topic,review.language));
    }
    if(!(data.due||[]).length) addText($('review-queue'),'p','Your next reviews will appear here after practice.','muted');
    for(const path of data.paths || []) {
      const section=document.createElement('section'); addText(section,'h3',path.title);
      for(const topic of path.topics) {
        const completed=(data.completed_topics||[]).some(item=>item.topic===topic && item.language===selectedLanguage);
        const button=addText(section,'button',(completed?'✓ ':'')+topic,'path-topic'); button.type='button';
        button.addEventListener('click',()=>chooseTopic(topic));
      }
      $('learning-paths').append(section);
    }
  } catch(error) { $('study-stats').textContent=error.message; }
}
$('save-goal').addEventListener('click',()=>perform('Saving daily goal…',async()=>{await post('/api/goal',{goal:Number($('daily-goal').value)}); await refreshDashboard();}));
$('export-data').addEventListener('click',async()=>{
  try {
    await saveDraft();
    const response=await fetch('/api/export'); if(!response.ok) throw new Error('Export failed.');
    const blob=new Blob([JSON.stringify(await response.json(),null,2)],{type:'application/json'});
    const link=document.createElement('a'); link.href=URL.createObjectURL(blob); link.download='am-progress.json'; link.click();
    setTimeout(()=>URL.revokeObjectURL(link.href),1000);
  } catch(error) {showError(error.message);}
});
$('delete-data').addEventListener('click',()=>{
  if(!confirm('Delete all saved sessions, drafts, progress, and goals on this machine? Export a backup first if needed.')) return;
  perform('Deleting saved study data…',async()=>{
    await post('/api/data/clear',{}); session=null; screen('setup'); await refreshDashboard();
  });
});
refreshDashboard();
