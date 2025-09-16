// Base URL config
export const base_url = localStorage.getItem('erp_base_url') || 'http://127.0.0.1:8000/erp/api';

export function setBaseUrl(url){
  localStorage.setItem('erp_base_url', url);
  showToast('Saved base_url: ' + url);
}

export async function fetchJSON(path, opts={}){
  const res = await fetch(`${base_url}${path}`, {
    headers:{ 'Content-Type':'application/json', ...(opts.headers||{}) },
    ...opts
  });
  const ct = res.headers.get('content-type')||'';
  let data=null;
  if (ct.includes('application/json')) data = await res.json();
  else data = await res.text();
  if (!res.ok) throw { status: res.status, data };
  return data;
}

export const $ = sel => document.querySelector(sel);
export const $$ = sel => [...document.querySelectorAll(sel)];

export function showToast(msg){
  let t = document.querySelector('.toast');
  if(!t){
    t=document.createElement('div');
    t.className='toast';
    document.body.appendChild(t);
  }
  t.textContent=msg;
  t.style.display='block';
  setTimeout(()=>t.style.display='none', 2500);
}

export function formToJSON(fd){
  const obj={};
  for (const [k,v] of fd.entries()) obj[k]=v;
  return obj;
}

export function setFormHandlers(formSel, submit){
  const form = $(formSel);
  form?.addEventListener('submit', async e=>{
    e.preventDefault();
    try{ await submit(new FormData(form)); }
    catch(err){ alert(JSON.stringify(err.data||err)); }
  });
}

export function setBaseUrlForm(sel){
  const f = $(sel); if(!f) return;
  f.base_url.value = base_url;
  f.addEventListener('submit', e=>{
    e.preventDefault();
    setBaseUrl(f.base_url.value);
  });
}

export function geolocate({latSel,lngSel,accSel}){
  if (!('geolocation' in navigator)) { alert('Trình duyệt không hỗ trợ GPS'); return; }
  navigator.geolocation.getCurrentPosition(pos=>{
    const { latitude, longitude, accuracy } = pos.coords;
    if(latSel) document.querySelector(latSel).value = latitude.toFixed(6);
    if(lngSel) document.querySelector(lngSel).value = longitude.toFixed(6);
    if(accSel) document.querySelector(accSel).value = Math.round(accuracy);
    showToast('Đã lấy vị trí hiện tại');
  }, err=>{ alert('Không lấy được vị trí: '+err.message); }, { enableHighAccuracy:true, timeout:10000 });
}
