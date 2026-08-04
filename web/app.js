const state={manifest:null,report:null,lang:localStorage.getItem('signal-lang')||'vi',category:'all',query:''};
const copy={
 vi:{edition:'BẢN TIN HẰNG NGÀY',headlineA:'Hiểu những tín hiệu',headlineB:'đang định hình ngày mai.',dek:'Công nghệ, mã nguồn mở, thị trường và các nhu cầu thiết yếu — được chọn lọc và giải thích bằng hai ngôn ngữ.',markets:'Thị trường',reference:'Dữ liệu tham khảo',archive:'Kho bản tin',selectDate:'Chọn ngày',pipeline:'Tình trạng pipeline',topStories:'Tin đáng chú ý',searchLabel:'Tìm kiếm',emptyTitle:'Không tìm thấy nội dung',emptyText:'Hãy thử ngày hoặc bộ lọc khác.',disclaimer:'Thông tin chỉ mang tính tham khảo, không phải lời khuyên đầu tư.',healthy:'Hoạt động tốt',warnings:'Có cảnh báo',stories:'tin được chọn lọc',all:'Tất cả',technology:'Công nghệ',github:'GitHub',finance:'Tài chính',society:'Xã hội',source:'Nguồn'},
 en:{edition:'DAILY INTELLIGENCE',headlineA:'Read the signals',headlineB:'shaping tomorrow.',dek:'Technology, open source, markets and essential needs — curated and explained in two languages.',markets:'Markets',reference:'Reference data',archive:'Edition archive',selectDate:'Select date',pipeline:'Pipeline status',topStories:'Top stories',searchLabel:'Search',emptyTitle:'No stories found',emptyText:'Try another date or filter.',disclaimer:'Information only. This is not investment advice.',healthy:'Operating normally',warnings:'Warnings detected',stories:'curated stories',all:'All',technology:'Technology',github:'GitHub',finance:'Finance',society:'Society',source:'Source'}
};
const $=selector=>document.querySelector(selector);
const esc=value=>String(value??'').replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
const dateLabel=value=>new Intl.DateTimeFormat(state.lang==='vi'?'vi-VN':'en-GB',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(value+'T12:00:00Z'));

async function init(){
 try{state.manifest=await fetch('/api/editions',{cache:'no-store'}).then(check);renderDates();await loadDate(new URLSearchParams(location.search).get('date')||state.manifest.latest)}
 catch(error){$('#storyList').innerHTML=`<div class="empty-state"><h3>${esc(error.message)}</h3><p>Run <code>python -m daily_news.server</code> to start the API and website.</p></div>`}
 bind();applyLanguage();applyTheme(localStorage.getItem('signal-theme')||'light');
}
const check=response=>{if(!response.ok)throw new Error(`Unable to load data (${response.status})`);return response.json()};
async function loadDate(date){
 if(!date)return;
 $('#storyList').setAttribute('aria-busy','true');
 try{state.report=await fetch(`/api/editions/${date}`,{cache:'no-store'}).then(check);history.replaceState({},'',`?date=${date}`);state.category='all';state.query='';$('#searchInput').value='';renderDates();renderAll()}
 finally{$('#storyList').removeAttribute('aria-busy')}
}
function renderDates(){
 const dates=state.manifest?.dates||[];const active=state.report?.date||state.manifest?.latest;
 $('#dateSelect').innerHTML=dates.map(d=>`<option value="${d}" ${d===active?'selected':''}>${dateLabel(d)}</option>`).join('');
 $('#dateList').innerHTML=dates.slice(0,8).map(d=>`<button class="${d===active?'active':''}" data-date="${d}">${dateLabel(d)}</button>`).join('');
}
function renderAll(){if(!state.report)return;$('#heroDate').textContent=dateLabel(state.report.date);renderMarkets();renderFilters();renderStories();const warning=state.report.warnings?.length>0;$('#statusDot').classList.toggle('warning',warning);$('#statusText').textContent=copy[state.lang][warning?'warnings':'healthy']}
function renderMarkets(){
 const rows=state.report.markets||[];$('#markets').innerHTML=rows.length?rows.map(m=>`<div class="market-card"><span>${esc(m.name)} · ${esc(m.symbol)}</span><strong>${Number(m.price).toLocaleString(state.lang==='vi'?'vi-VN':'en-US',{maximumFractionDigits:4})}</strong><em class="${m.change_pct>=0?'positive':'negative'}">${m.change_pct>=0?'↑':'↓'} ${Math.abs(m.change_pct).toFixed(2)}% ${esc(m.currency)}</em></div>`).join(''):`<div class="market-card"><span>—</span><strong>No data</strong></div>`;
}
function renderFilters(){const cats=['all','technology','github','finance','society'];$('#filters').innerHTML=cats.map(c=>`<button class="${state.category===c?'active':''}" data-category="${c}" aria-pressed="${state.category===c}">${copy[state.lang][c]}</button>`).join('')}
function renderStories(){
 const q=state.query.toLocaleLowerCase();const rows=(state.report.items||[]).filter(x=>(state.category==='all'||x.category===state.category)&&`${x.title_vi} ${x.title_en} ${x.summary_vi} ${x.summary_en} ${x.source}`.toLocaleLowerCase().includes(q));
 $('#resultCount').textContent=`${rows.length} ${copy[state.lang].stories}`;$('#emptyState').hidden=rows.length>0;
 $('#storyList').innerHTML=rows.map((x,i)=>{const title=state.lang==='vi'?(x.title_vi||x.title):(x.title_en||x.title);const summary=state.lang==='vi'?(x.summary_vi||x.description):(x.summary_en||x.description);const repo=x.category==='github'?`<div class="repo-stats"><span>★ ${esc(x.meta?.stars||0)}</span><span>${esc(x.meta?.language||'N/A')}</span><span>+${esc(x.meta?.stars_per_day||0)}/day</span></div>`:'';return `<article class="story" style="animation-delay:${Math.min(i*35,280)}ms"><div class="story-index">${String(i+1).padStart(2,'0')}</div><div><span class="story-category">${copy[state.lang][x.category]||x.category}</span><h3><a href="${esc(x.url)}" target="_blank" rel="noopener noreferrer">${esc(title)}</a></h3><p>${esc(summary)}</p>${repo}</div><div class="story-meta"><strong>${copy[state.lang].source}</strong><span>${esc(x.source)}</span><span>${esc(x.market==='vietnam'?'Vietnam':'Global')}</span></div></article>`}).join('');
}
function applyLanguage(){document.documentElement.lang=state.lang;document.querySelectorAll('[data-i18n]').forEach(el=>el.textContent=copy[state.lang][el.dataset.i18n]);document.querySelectorAll('[data-lang]').forEach(el=>el.classList.toggle('active',el.dataset.lang===state.lang));$('#searchInput').placeholder=$('#searchInput').dataset[`placeholder${state.lang[0].toUpperCase()+state.lang.slice(1)}`];renderDates();renderAll()}
function applyTheme(theme){document.documentElement.dataset.theme=theme;localStorage.setItem('signal-theme',theme)}
function bind(){
 document.addEventListener('click',e=>{const date=e.target.closest('[data-date]');const lang=e.target.closest('[data-lang]');const category=e.target.closest('[data-category]');if(date)loadDate(date.dataset.date);if(lang){state.lang=lang.dataset.lang;localStorage.setItem('signal-lang',state.lang);applyLanguage()}if(category){state.category=category.dataset.category;renderFilters();renderStories()}});
 $('#dateSelect').addEventListener('change',e=>loadDate(e.target.value));$('#searchInput').addEventListener('input',e=>{state.query=e.target.value;renderStories()});$('#themeButton').addEventListener('click',()=>applyTheme(document.documentElement.dataset.theme==='dark'?'light':'dark'));
}
init();
