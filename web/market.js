(()=>{
  const api='https://data-api.binance.vision/api/v3';
  const wsBase='wss://data-stream.binance.vision/ws';
  const el=id=>document.getElementById(id);
  const market={symbol:'BTCUSDT',interval:'5m',socket:null,chart:null,candles:null,volume:null,data:[],paused:false,retry:0};
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
    updateKpis(market.data.at(-1));el('marketVolume').textContent=num(ticker.quoteVolume,0)+' USDT';renderTable();
  }
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
  function translate(){document.querySelectorAll('[data-market-vi]').forEach(x=>x.textContent=x.dataset[vi()?'marketVi':'marketEn']);setState(market.paused?'paused':market.socket?.readyState===1?'live':'connecting');renderTable()}
  function bind(){
    el('marketSymbol').addEventListener('change',e=>{market.symbol=e.target.value;load()});
    el('marketIntervals').addEventListener('click',e=>{const b=e.target.closest('[data-interval]');if(!b)return;market.interval=b.dataset.interval;document.querySelectorAll('[data-interval]').forEach(x=>x.classList.toggle('active',x===b));load()});
    el('streamToggle').addEventListener('click',()=>{market.paused=!market.paused;el('streamToggle').setAttribute('aria-pressed',String(market.paused));el('streamToggle').querySelector('span').textContent=market.paused?(vi()?'Tiếp tục':'Resume'):(vi()?'Tạm dừng':'Pause');if(market.paused){disconnect();setState('paused')}else connect()});
    el('chartRetry').addEventListener('click',load);
    new MutationObserver(()=>{if(!market.chart)return;const c=colors();market.chart.applyOptions({layout:{background:{type:'solid',color:c.background},textColor:c.text},grid:{vertLines:{color:c.grid},horzLines:{color:c.grid}},rightPriceScale:{borderColor:c.border},timeScale:{borderColor:c.border}});translate()}).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme','lang']});
  }
  window.addEventListener('DOMContentLoaded',()=>{translate();bind();if(initChart())load()});window.addEventListener('beforeunload',disconnect);
})();
