'use strict';
const $ = (id) => document.getElementById(id);
const state = { profile: null, jobs: [], tracker: {}, sources: [], filter: 'all', scope: 'all', industry: 'all', scan: null, renderLimit: 60 };
const ACTIVE = ['saved', 'applied', 'interview', 'offer', 'rejected', 'closed', 'dismissed'];
const STATUS_LABELS = {saved:'Saved',applied:'Applied',interview:'Interview',offer:'Offer',rejected:'Rejected',closed:'Closed',dismissed:'Dismissed'};

async function request(path, body) {
  const opts = body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)};
  const response = await fetch(path, opts);
  let data; try { data = await response.json(); } catch { throw new Error('Unexpected server response'); }
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}
function clear(node) { node.replaceChildren(); }
function toast(message, error = false) {
  const node = $('notice'); node.textContent = message; node.hidden = false; node.className = error ? 'error' : '';
}
function money(number) { return typeof number === 'number' ? '£' + number.toLocaleString('en-GB') : null; }
function salary(job) {
  const a = money(job.salary_min), b = money(job.salary_max);
  if (a && b) return a === b ? a + ' annual' : `${a}–${b} annual`;
  if (a) return `From ${a} (advertised)`;
  if (b) return `Up to ${b} (advertised)`;
  return 'Salary not confirmed';
}
function switchTab(target) {
  for (const section of ['discover','tracker','settings']) $(section).hidden = section !== target;
  for (const button of document.querySelectorAll('[data-tab]')) button.classList.toggle('active', button.dataset.tab === target);
  if (target === 'tracker') renderTracker();
}
function appendMeta(parent, text) { parent.append(el('span','',text)); }
function jobCard(job) {
  const card = el('article','job');
  const head = el('div','job-head');
  const left = el('div');
  left.append(el('div','company-name',job.company),el('h3','',job.title));
  const meta = el('div','job-meta');
  appendMeta(meta,job.location || 'Location not stated');
  if (job.workplace_type && job.workplace_type !== 'unknown') appendMeta(meta, job.workplace_type);
  appendMeta(meta, salary(job));
  if (job.industry) {
    const sector = (state.scan?.industries || []).find(item => item.id === job.industry);
    appendMeta(meta, sector?.label || 'Unclassified');
  }
  left.append(meta);
  const tag = el('span','tag ' + (job.verdict === 'REVIEW' ? 'review' : job.verdict !== 'SHORTLIST' ? 'rejected' : ''),
    job.verdict === 'SHORTLIST' ? 'Strong first match' : job.verdict === 'REVIEW' ? 'Needs review' : 'Outside my preferences');
  head.append(left,tag);card.append(head);
  const reasons = el('ul','reasons');
  for (const reason of job.reasons || []) reasons.append(el('li','',reason));
  if ((job.reasons || []).length) card.append(reasons);
  const buttons = el('div','job-actions');
  if (job.source !== 'demo') {
    const link = el('a','btn ghost',job.source === 'adzuna' ? 'View on Adzuna' : job.source === 'reed' ? 'View on Reed' : job.source === 'website' ? 'Company careers page' : 'Official advert');
    link.href=job.url; link.target='_blank'; link.rel='noopener noreferrer'; buttons.append(link);
  }
  const save = el('button','btn primary',state.tracker[job.id] ? 'Saved ✓' : 'Save job');
  save.type = 'button';
  save.addEventListener('click',async()=>{
    if (job.source === 'demo') { toast('Example vacancies cannot be saved as real jobs.',true);return; }
    if (state.tracker[job.id]) { switchTab('tracker');return; }
    try {
      const data = await request('/api/tracker',{job,status:'saved',notes:''});
      state.tracker=data.tracker;updateSavedCount();renderJobs();toast('Saved to your private application tracker.');
    } catch(e) { toast(e.message,true); }
  });
  if (job.source === 'demo') { save.disabled = true; save.textContent = 'Example only'; }
  buttons.append(save);card.append(buttons);
  if (job.description) {
    const details = el('details','details');
    details.append(el('summary','','Read description'));
    details.append(el('div','job-description',job.description));
    card.append(details);
  }
  return card;
}
function renderJobs() {
  const container = $('jobList');clear(container);
  const term = $('searchInput').value.trim().toLowerCase();
  const filtered = state.jobs.filter(job=>{
    const allow = state.filter === 'all' || (state.filter === 'relevant' && ['SHORTLIST','REVIEW'].includes(job.verdict)) ||
      (state.filter === 'shortlist' && job.verdict === 'SHORTLIST') || (state.filter === 'review' && job.verdict === 'REVIEW');
    const industryOK = state.industry === 'all' || job.industry === state.industry;
    const label = (state.scan?.industries || []).find(item => item.id === job.industry)?.label || '';
    return allow && industryOK && [job.title,job.company,job.location,job.description,label].some(item=>String(item || '').toLowerCase().includes(term));
  });
  if (!state.scan) return;
  $('resultsSummary').hidden=false;
  const visible = Math.min(filtered.length, state.renderLimit);
  $('resultsSummary').textContent=`Showing ${visible} of ${filtered.length} matching results, from ${state.jobs.length} vacancies discovered across enabled sources.`;
  if (!filtered.length) {
    const empty = el('div','empty');
    empty.append(el('h3','','No results in this view'),el('p','', 'No vacancies from the scanned sources meet these filters. Try another industry or add more employer sources.'));
    container.append(empty);return;
  }
  for (const job of filtered.slice(0, state.renderLimit)) container.append(jobCard(job));
  if (filtered.length > state.renderLimit) {
    const more = el('button','btn ghost',`Load more jobs (${filtered.length - state.renderLimit} remaining)`);
    more.type = 'button';
    more.addEventListener('click',()=>{state.renderLimit += 60;renderJobs();});
    container.append(more);
  }
}
function renderIndustries() {
  const rail = $('industryRail'); clear(rail);
  if (!state.scan) return;
  const industries = state.scan.industries || [];
  const available = industries.filter(item => item.count > 0);
  const total = state.jobs.length;
  const choices = [{id:'all', label:'All industries', count:total, matched:state.jobs.filter(job=>['SHORTLIST','REVIEW'].includes(job.verdict)).length}, ...available];
  for (const category of choices) {
    const btn = el('button', 'industry-card' + (state.industry === category.id ? ' selected' : ''));
    btn.type='button'; btn.dataset.industry=category.id;
    btn.setAttribute('aria-pressed', String(state.industry === category.id));
    btn.append(el('span','industry-name',category.label),el('strong','industry-count',String(category.count) + ' jobs'),el('span','industry-match',category.matched + ' potential matches'));
    btn.addEventListener('click',()=>{state.industry=category.id;state.renderLimit=60;renderIndustries();renderJobs();});
    rail.append(btn);
  }
  const current = choices.find(c=>c.id===state.industry) || choices[0];
  $('industrySummary').textContent = current.id === 'all' ?
    `Showing all ${total} discovered vacancies across ${available.length} categorised groups.` :
    `${current.count} scanned vacancies in ${current.label}; ${current.matched} potentially relevant to your preferences.`;
}
function showScan(scan) {
  state.scan=scan;state.jobs=scan.jobs || []; state.industry='all';state.renderLimit=60;
  $('stats').hidden=false;$('filters').hidden=false;$('industrySection').hidden=false;
  $('countShortlist').textContent=scan.counts.SHORTLIST || 0;
  $('countReview').textContent=scan.counts.REVIEW || 0;
  $('countSources').textContent=scan.demo ? 'Demo' : `${scan.sources_reached}/${scan.source_count}`;
  $('discoveryCount').textContent=String((scan.jobs || []).length);
  const source = $('sourceStatus');
  source.classList.toggle('demo',Boolean(scan.demo));
  const stamp = new Date(scan.checked_at).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'});
  if (scan.demo) source.textContent='DEMONSTRATION — These are fictional jobs. No actual vacancies have been checked.';
  else source.textContent=`Checked at ${stamp}. Reached ${scan.sources_reached} of ${scan.source_count} enabled sources. ${scan.sources_disabled || 0} sources disabled. ${scan.excluded_non_uk || 0} overseas-only listings excluded. ${scan.coverage_note}` + (scan.errors.length ? ` ${scan.errors.length} source or record error(s): ${scan.errors.join(' | ')}` : '');
  const health = $('coverageHealth');
  if (health) {
    clear(health);
    for (const row of scan.source_health || []) {
      health.append(el('li', row.status === 'ok' ? 'ok' : 'error',
        `${row.name} (${row.provider}): ${row.status === 'ok' ? row.raw_count + ' returned' : 'unavailable — ' + row.error}`));
    }
    const detail = $('coverageDetails'); if (detail) detail.hidden = !health.children.length;
  }
  renderIndustries();renderJobs();
}
function setScope(scope, {resetText = false} = {}) {
  state.scope = scope === 'matches' ? 'matches' : 'all';
  state.filter = state.scope === 'all' ? 'all' : 'relevant';
  if (resetText) { $('searchInput').value=''; state.industry='all'; }
  state.renderLimit=60;
  for (const [id, current] of [['searchAllBtn', 'all'], ['searchMatchesBtn', 'matches']]) {
    const button=$(id); button.classList.toggle('selected', state.scope === current);
    button.setAttribute('aria-pressed', String(state.scope === current));
  }
  for (const button of document.querySelectorAll('[data-filter]'))
    button.classList.toggle('active', button.dataset.filter === state.filter);
  $('scopeDescription').textContent = state.scope === 'all' ?
    'Searching everything means all configured sources, not every vacancy advertised in the UK. You can narrow results afterwards by industry or keyword.' :
    'Searches every connected source, then displays strong matches and roles needing review. You can still switch to All vacancies.';
  if (state.scan) { renderIndustries();renderJobs(); }
}
async function runScan(scope = 'all', demo = false) {
  setScope(scope, {resetText:true});
  const buttons=[$('searchAllBtn'),$('searchMatchesBtn'),$('demoBtn')];
  buttons.forEach(button => {button.disabled = true;});
  $('sourceStatus').textContent = 'Checking every configured source across all industries…';
  try { showScan(await request('/api/jobs' +(demo ? '?demo=1':''))); }
  catch(e) { toast(`Couldn't complete the scan: ${e.message}`,true); $('sourceStatus').textContent = 'Source scan unsuccessful. Existing results, if any, are still available.'; }
  finally { buttons.forEach(button => {button.disabled = false;}); }
}
function updateSavedCount(){ $('savedCount').textContent=String(Object.keys(state.tracker).length); }
function renderTracker(){
  const target=$('trackerList');clear(target);const items=Object.values(state.tracker).sort((a,b)=>String(b.updated_at).localeCompare(String(a.updated_at)));
  if (!items.length) { const card=el('div','empty');card.append(el('h3','','No saved jobs yet'),el('p','','Save a real vacancy from Discover jobs to track your application here.'));const button=el('button','btn primary','Discover jobs');button.addEventListener('click',()=>switchTab('discover'));card.append(button);target.append(card);return; }
  for (const job of items) {
    const card=el('article','job');card.append(el('div','company-name',job.company),el('h3','',job.title));
    const meta=el('div','job-meta'); appendMeta(meta,job.location || 'Location not stated');appendMeta(meta,salary(job));card.append(meta);
    const ctr=el('div','tracker-controls');const side=el('label','','Application status');
    const select=el('select');for(const s of ACTIVE){const option=el('option','',STATUS_LABELS[s]);option.value=s;option.selected=job.status===s;select.append(option);}side.append(select);
    const note=el('label','','My notes');const textarea=el('textarea');textarea.value=job.notes || '';textarea.maxLength=2500;textarea.placeholder='Interview dates, hiring manager, questions, next steps...';note.append(textarea);
    ctr.append(side,note);card.append(ctr);
    const actions=el('div','tracker-footer');const save=el('button','btn primary','Save changes');save.addEventListener('click',async()=>{
      try { const result=await request('/api/tracker',{job,status:select.value,notes:textarea.value});state.tracker=result.tracker;updateSavedCount();renderTracker();toast('Application updated.'); }
      catch(e){toast(e.message,true);}
    });const remove=el('button','btn danger','Remove');remove.addEventListener('click',async()=>{
      if (!confirm(`Remove ${job.title} at ${job.company} from your private tracker?`)) return;
      try {const result=await request('/api/tracker',{job,status:'remove'});state.tracker=result.tracker;updateSavedCount();renderTracker();renderJobs();toast('Job removed.');}
      catch(e){toast(e.message,true);}
    });const link=el('a','btn ghost','Visit advert');link.href=job.url;link.target='_blank';link.rel='noopener noreferrer';
    actions.append(save,link,remove);card.append(actions);target.append(card);
  }
}
function commas(id){return $(id).value.split(',').map(x=>x.trim()).filter(Boolean);}
function fillProfile(profile){
  $('roles').value=(profile.target_roles || []).join(', ');$('related').value=(profile.related_terms || []).join(', ');
  $('minSalary').value=profile.minimum_basic_salary_gbp ?? '';$('preferredSalary').value=profile.preferred_basic_salary_gbp ?? '';
  $('homeBase').value=profile.home_base || '';$('nearby').value=(profile.nearby_places || []).join(', ');
  $('hybrid').value=(profile.hybrid_review_places || []).join(', ');$('excluded').value=(profile.excluded_commute_places || []).join(', ');
  $('excludedRoles').value=(profile.excluded_title_terms || []).join(', ');$('remoteFirst').checked=Boolean(profile.remote_first);
}
function numOrNull(id){const v=$(id).value.trim();return v ? Number(v) : null;}
async function saveProfile(event){
  event.preventDefault();const profile={...state.profile,
    target_roles:commas('roles'),related_terms:commas('related'),minimum_basic_salary_gbp:numOrNull('minSalary'),
    preferred_basic_salary_gbp:numOrNull('preferredSalary'),home_base:$('homeBase').value.trim(),
    nearby_places:commas('nearby'),hybrid_review_places:commas('hybrid'),excluded_commute_places:commas('excluded'),
    excluded_title_terms:commas('excludedRoles'),remote_first:$('remoteFirst').checked
  };
  try{await request('/api/profile',profile);state.profile=profile;state.scan=null;state.jobs=[];$('filters').hidden=true;$('stats').hidden=true;
    clear($('jobList'));const empty=el('div','empty');empty.append(el('h3','','Preferences saved'),el('p','','Now run a new scan. Your previous results were cleared because matching rules changed.'));$('jobList').append(empty);
    $('industrySection').hidden=true;state.industry='all';$('resultsSummary').hidden=true;
    $('sourceStatus').textContent='Preferences updated. Run a live scan to refresh your matches.';switchTab('discover');toast('Your preferences were saved locally.');
  }catch(e){toast(e.message,true);}
}
function renderSources(){
  const target=$('sourceList');clear(target);
  for(const src of state.sources){
    const item=el('div','source-item');const description=el('div');
    description.append(el('strong','',src.name),el('span','',` · ${src.provider} · ${src.sector || 'Unclassified'}`));
    const remove=el('button','btn ghost','Remove');remove.type='button';remove.addEventListener('click',async()=>{
      if(!confirm(`Remove ${src.name} from your scan sources?`))return;
      try{const result=await request('/api/sources',{action:'remove',provider:src.provider,board:src.board,url:src.url});state.sources=result.sources;renderSources();toast('Employer source removed. Future scans will use the updated list.');}
      catch(e){toast(e.message,true);}
    });item.append(description,remove);target.append(item);
  }
  if(!state.sources.length)target.append(el('p','muted','No employers configured. Add a careers source below.'));
}
async function addSource(event){
  event.preventDefault();
  try{const result=await request('/api/sources',{action:'add',name:$('newSourceName').value.trim(),url:$('newSourceUrl').value.trim(),job_path_prefix:$('newJobPathPrefix').value.trim(),sector:$('newSourceSector').value});
    state.sources=result.sources;renderSources();$('sourceForm').reset();toast('Employer added to your local sources. Run a new scan to search it.');}
  catch(e){toast(e.message,true);}
}
async function setup(){
  for(const button of document.querySelectorAll('[data-tab]'))button.addEventListener('click',()=>switchTab(button.dataset.tab));
  for(const button of document.querySelectorAll('[data-filter]'))button.addEventListener('click',()=>{
    const selection=button.dataset.filter;setScope(selection === 'all' ? 'all' : 'matches');
    state.filter=selection;for(const b of document.querySelectorAll('[data-filter]'))b.classList.toggle('active',b===button);renderJobs();
  });
  $('searchAllBtn').addEventListener('click',()=>runScan('all'));
  $('searchMatchesBtn').addEventListener('click',()=>runScan('matches'));
  $('demoBtn').addEventListener('click',()=>runScan('all',true));
  $('searchInput').addEventListener('input',()=>{state.renderLimit=60;renderJobs();});$('goPreferences').addEventListener('click',()=>switchTab('settings'));
  $('industryPrev').addEventListener('click',()=>$('industryRail').scrollBy({left:-410,behavior:'smooth'}));
  $('industryNext').addEventListener('click',()=>$('industryRail').scrollBy({left:410,behavior:'smooth'}));
  $('preferencesForm').addEventListener('submit',saveProfile);$('sourceForm').addEventListener('submit',addSource);
  try{const [profile,tracker,sourceData]=await Promise.all([request('/api/profile'),request('/api/tracker'),request('/api/sources')]);state.profile=profile;state.tracker=tracker;state.sources=sourceData.sources;
    fillProfile(profile);updateSavedCount();renderTracker();renderSources();}
  catch(e){toast(`Couldn't load local settings: ${e.message}`,true);}
}
setup();
