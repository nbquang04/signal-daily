(()=>{
  const api='https://data-api.binance.vision/api/v3';
  const wsBase='wss://data-stream.binance.vision/ws';
  const el=id=>document.getElementById(id);
  const safe=value=>String(value??'').replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const market={symbol:'BTCUSDT',interval:'5m',socket:null,chart:null,candles:null,volume:null,data:[],paused:false,retry:0};
  const instrumentMeta={PAXGUSDT:{gold:true,name:'PAX Gold'},XAUTUSDT:{gold:true,name:'Tether Gold'},BTCUSDT:{name:'Bitcoin'},ETHUSDT:{name:'Ethereum'},BNBUSDT:{name:'BNB'},SOLUSDT:{name:'Solana'},XRPUSDT:{name:'XRP'}};
  const vi=()=>document.documentElement.lang!=='en';
  const num=(value,digits=2)=>Number(value).toLocaleString(vi()?'vi-VN':'en-US',{maximumFractionDigits:digits});
  const priceDigits=value=>Number(value)>=1000?2:Number(value)>=1?4:6;
  const colors=()=>{const dark=document.documentElement.dataset.theme==='dark';return{background:dark?'#111214':'#fff',text:dark?'#d7d7d9':'#37373b',grid:dark?'#26272b':'#ececef',border:dark?'#35363a':'#d9d9dd'}};
  function initChart(){
    if(!window.LightweightCharts){showError(vi()?'Không tải được thư viện biểu đồ.':'Chart library failed to load.');return false}
    const c=colors();market.chart=LightweightCharts.createChart(el('marketChart'),{autoSize:true,layout:{background:{type:'solid',color:c.background},textColor:c.text,attributionLogo:false},grid:{vertLines:{color:c.grid},horzLines:{color:c.grid}},rightPriceScale:{borderColor:c.border},timeScale:{borderColor:c.border,timeVisible:true,secondsVisible:false},crosshair:{mode:LightweightCharts.CrosshairMode.Normal},localization:{locale:vi()?'vi-VN':'en-US'}});
    market.candles=market.chart.addSeries(LightweightCharts.CandlestickSeries,{upColor:'#149174',downColor:'#d64747',wickUpColor:'#149174',wickDownColor:'#d64747',borderVisible:false,priceFormat:{type:'price',precision:2,minMove:.01}});
    market.volume=market.chart.addSeries(LightweightCharts.HistogramSeries,{priceFormat:{type:'volume'},priceScaleId:'volume',lastValueVisible:false,priceLineVisible:false});
    market.volume.priceScale().applyOptions({scaleMargins:{top:.82,bottom:0}});
    new ResizeObserver(()=>market.chart.timeScale().fitContent()).observe(el('marketChart'));
    return true;
  }
  const candle=row=>({time:Number(row[0])/1000,open:Number(row[1]),high:Number(row[2]),low:Number(row[3]),close:Number(row[4]),volume:Number(row[5])});
  async function load(){
    disconnect();el('chartLoading').hidden=false;el('chartError').hidden=true;setState('connecting');
    try{
      const [klines,ticker]=await Promise.all([
        fetch(`${api}/klines?symbol=${market.symbol}&interval=${market.interval}&limit=300`,{cache:'no-store'}).then(check),
        fetch(`${api}/ticker/24hr?symbol=${market.symbol}`,{cache:'no-store'}).then(check)
      ]);
      market.data=klines.map(candle);renderAll(ticker);el('chartLoading').hidden=true;market.chart.timeScale().fitContent();connect();
    }catch(error){showError(error.message)}
  }
  const check=response=>{if(!response.ok)throw new Error(`Binance API ${response.status}`);return response.json()};
  function renderAll(ticker){
    const precision=priceDigits(market.data.at(-1)?.close||0);market.candles.applyOptions({priceFormat:{type:'price',precision,minMove:10**-precision}});
    market.candles.setData(market.data.map(({time,open,high,low,close})=>({time,open,high,low,close})));
    market.volume.setData(market.data.map(x=>({time:x.time,value:x.volume,color:x.close>=x.open?'rgba(20,145,116,.36)':'rgba(214,71,71,.34)'})));
    updateKpis(market.data.at(-1));el('marketVolume').textContent=num(ticker.quoteVolume,0)+' USDT';renderTable();renderInstrumentNotice();
  }
  function renderInstrumentNotice(){const meta=instrumentMeta[market.symbol]||{};el('instrumentNotice').innerHTML=meta.gold?(vi()?`<strong>${meta.name}</strong> là token được bảo chứng bằng vàng và giao dịch 24/7. Giá có thể lệch XAU/USD spot do thanh khoản và cung cầu crypto.`:`<strong>${meta.name}</strong> is a gold-backed token trading 24/7. It may diverge from spot XAU/USD because of crypto liquidity and demand.`):(vi()?`<strong>${meta.name||market.symbol}</strong> là tài sản crypto giao dịch 24/7 trên Binance Spot.`:`<strong>${meta.name||market.symbol}</strong> is a crypto asset trading 24/7 on Binance Spot.`)}
  function connect(){
    if(market.paused)return setState('paused');
    market.socket=new WebSocket(`${wsBase}/${market.symbol.toLowerCase()}@kline_${market.interval}`);
    market.socket.onopen=()=>{market.retry=0;setState('live')};
    market.socket.onmessage=event=>{if(market.paused)return;const k=JSON.parse(event.data).k;const next={time:k.t/1000,open:Number(k.o),high:Number(k.h),low:Number(k.l),close:Number(k.c),volume:Number(k.v)};const last=market.data.at(-1);if(last?.time===next.time)market.data[market.data.length-1]=next;else market.data.push(next);market.data=market.data.slice(-500);market.candles.update(next);market.volume.update({time:next.time,value:next.volume,color:next.close>=next.open?'rgba(20,145,116,.36)':'rgba(214,71,71,.34)'});updateKpis(next);if(k.x)renderTable()};
    market.socket.onerror=()=>setState('connecting');market.socket.onclose=()=>{if(!market.paused&&market.retry<5){market.retry++;setTimeout(connect,Math.min(1000*2**market.retry,15000))}};
  }
  function disconnect(){if(market.socket){market.socket.onclose=null;market.socket.close();market.socket=null}}
  function updateKpis(x){if(!x)return;const change=(x.close-x.open)/x.open*100;el('marketPrice').textContent=num(x.close,priceDigits(x.close))+' USDT';el('marketChange').textContent=`${change>=0?'+':''}${change.toFixed(2)}%`;el('marketChange').className=change>=0?'positive':'negative';el('marketUpdated').textContent=new Intl.DateTimeFormat(vi()?'vi-VN':'en-GB',{hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date())}
  function renderTable(){el('ohlcTable').innerHTML=market.data.slice(-10).reverse().map(x=>`<tr><td>${new Date(x.time*1000).toLocaleString(vi()?'vi-VN':'en-GB')}</td><td>${num(x.open,priceDigits(x.open))}</td><td>${num(x.high,priceDigits(x.high))}</td><td>${num(x.low,priceDigits(x.low))}</td><td>${num(x.close,priceDigits(x.close))}</td><td>${num(x.volume,2)}</td></tr>`).join('')}
  function setState(state){const box=document.querySelector('.stream-state');box.className=`stream-state ${state}`;el('streamLabel').textContent=state==='live'?(vi()?'Trực tiếp':'Live'):state==='paused'?(vi()?'Đã tạm dừng':'Paused'):(vi()?'Đang kết nối':'Connecting')}
  function showError(message){el('chartLoading').hidden=true;el('chartError').hidden=false;el('chartErrorText').textContent=message;setState('paused')}
  function translate(){document.querySelectorAll('[data-market-vi]').forEach(x=>x.textContent=x.dataset[vi()?'marketVi':'marketEn']);setState(market.paused?'paused':market.socket?.readyState===1?'live':'connecting');renderTable();renderInstrumentNotice()}
  window.renderMarketContext=(rows,lang)=>{const host=el('marketContextGrid');if(!host)return;const wanted=[['Gold','Vàng phản ứng ngược USD và lợi suất thực.','Gold often reacts inversely to USD and real yields.'],['USD/VND','Tỷ giá ảnh hưởng giá vàng quy đổi tại Việt Nam.','FX affects Vietnam-localized gold prices.'],['Crude Oil','Dầu là tín hiệu lạm phát và kỳ vọng lãi suất.','Oil signals inflation and rate expectations.'],['S&P 500','Risk-on/risk-off có thể dịch chuyển dòng tiền vào vàng.','Risk sentiment can shift flows into gold.'],['Bitcoin','So sánh nhu cầu tài sản khan hiếm và phòng hộ.','Compare scarce-asset and hedge demand.']];const found=wanted.map(([name,viText,enText])=>{const row=rows.find(x=>String(x.name||'').toLowerCase().includes(name.toLowerCase())||String(x.symbol||'').toLowerCase().includes(name.toLowerCase()));return row?{...row,note:lang==='en'?enText:viText}:null}).filter(Boolean);host.innerHTML=found.length?found.map(x=>`<article class="factor-card"><span>${safe(x.name)} · ${safe(x.symbol)}</span><strong>${num(x.price,4)} <em class="${x.change_pct>=0?'positive':'negative'}">${x.change_pct>=0?'+':''}${Number(x.change_pct).toFixed(2)}%</em></strong><small>${safe(x.note)}</small></article>`).join(''):`<article class="factor-card"><span>—</span><strong>${lang==='en'?'No context data':'Chưa có dữ liệu đối chiếu'}</strong></article>`};
  if(window.marketContextData)window.renderMarketContext(window.marketContextData.rows,window.marketContextData.lang);
  function bind(){
    el('marketSymbol').addEventListener('change',e=>{market.symbol=e.target.value;load()});
    el('marketIntervals').addEventListener('click',e=>{const b=e.target.closest('[data-interval]');if(!b)return;market.interval=b.dataset.interval;document.querySelectorAll('[data-interval]').forEach(x=>x.classList.toggle('active',x===b));load()});
    el('streamToggle').addEventListener('click',()=>{market.paused=!market.paused;el('streamToggle').setAttribute('aria-pressed',String(market.paused));el('streamToggle').querySelector('span').textContent=market.paused?(vi()?'Tiếp tục':'Resume'):(vi()?'Tạm dừng':'Pause');if(market.paused){disconnect();setState('paused')}else connect()});
    el('chartRetry').addEventListener('click',load);
    new MutationObserver(()=>{if(!market.chart)return;const c=colors();market.chart.applyOptions({layout:{background:{type:'solid',color:c.background},textColor:c.text},grid:{vertLines:{color:c.grid},horzLines:{color:c.grid}},rightPriceScale:{borderColor:c.border},timeScale:{borderColor:c.border}});translate()}).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme','lang']});
  }
  window.addEventListener('DOMContentLoaded',()=>{translate();bind();if(initChart())load()});window.addEventListener('beforeunload',disconnect);
})();
