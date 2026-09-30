/* Deterministic, read-only weekly agendas for explicit owner calendar lists. */
import http from 'node:http';
import {join} from 'node:path';

const PAGE_LIMIT=20, MAX_READS=25, MAX_DEPTH=4, MAX_DURATION_MS=120000;
const DATE=/^(\d{4})-(\d{2})-(\d{2})$/;
const dateFormat=new Intl.DateTimeFormat('en-US',{weekday:'long',month:'long',day:'numeric',year:'numeric'});
const timeFormat=new Intl.DateTimeFormat('en-US',{hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
const zoneFormat=new Intl.DateTimeFormat('en-US',{timeZoneName:'short'});

export function calendarWeekIntent(prompt,at=new Date()){
 if(typeof prompt!=='string'||!Number.isFinite(at?.getTime?.()))return null;
 const value=prompt.replace(/[’‘]/g,"'");
 const week=/\b(this|next)\s+week\b/i.exec(value);
 if(!week||!/\bmy\b/i.test(value)||!/\b(?:calendar|appointments?|meetings?|events?)\b/i.test(value)
   ||!/(?:\bwhat(?:'s| is) on\b|\blist\b|\bshow\b|\bagenda\b)/i.test(value)
   ||/\b(?:free|availability|available|conflicts?|cancel|add|create|move|reschedule|delete|rsvp|invite|search|find|only|except|excluding|where|location|details?|description|attendees?|organizer|join|links?)\b/i.test(value))return null;
 const mondayOffset=(at.getDay()+6)%7;
 const start=new Date(at.getFullYear(),at.getMonth(),at.getDate()-mondayOffset+(week[1].toLowerCase()==='next'?7:0));
 const end=new Date(start.getFullYear(),start.getMonth(),start.getDate()+7);
 return {start:start.getTime(),end:end.getTime()};
}

function eventStart(value){
 if(typeof value!=='string')return null;
 const match=DATE.exec(value);
 const parsed=match?new Date(Number(match[1]),Number(match[2])-1,Number(match[3])):new Date(value);
 if(match&&(parsed.getFullYear()!==Number(match[1])||parsed.getMonth()!==Number(match[2])-1||parsed.getDate()!==Number(match[3])))return null;
 return Number.isFinite(parsed.getTime())?parsed:null;
}
const cleanTitle=value=>String(value??'(Untitled event)').replace(/[\x00-\x1f\x7f]/g,' ').replace(/\s+/g,' ').trim().slice(0,300).replace(/[\\`*_\[\]()~]/g,'\\$&')||'(Untitled event)';
const zone=value=>zoneFormat.formatToParts(value).find(part=>part.type==='timeZoneName')?.value??'local time';
function eventLine(event,start){
 const allDay=event.allDay===true||DATE.test(event.start??'');
 const end=eventStart(event.end);
 const endDay=end&&dateFormat.format(end)!==dateFormat.format(start);
 const lastAllDay=end?new Date(end.getTime()-1):null;
 const allDaySpan=lastAllDay&&dateFormat.format(lastAllDay)!==dateFormat.format(start);
 const time=allDay?allDaySpan?`All day through ${dateFormat.format(lastAllDay)}`:'All day'
  :end?`${timeFormat.format(start)}–${endDay?dateFormat.format(end)+' ':''}${timeFormat.format(end)} ${zone(start)}`
  :`${timeFormat.format(start)} ${zone(start)} (end unavailable)`;
 return `- ${dateFormat.format(start)} · ${time} · ${cleanTitle(event.summary)}`;
}

export function createCalendarWeekAgenda({readEvents,clock=()=>Date.now()}={}){
 if(typeof readEvents!=='function')throw Error('calendar_reader_missing');
 return async(intent,signal)=>{
  if(!intent||!Number.isFinite(intent.start)||!Number.isFinite(intent.end)||intent.end<=intent.start)throw Error('calendar_week_invalid');
  const begun=clock();let reads=0;const found=new Map();
  async function collect(from,to,depth){
   if(signal?.aborted||clock()-begun>=MAX_DURATION_MS||++reads>MAX_READS)throw Error('calendar_week_incomplete');
   const page=await readEvents({calendar:'all',from:new Date(from).toISOString(),to:new Date(to).toISOString(),limit:PAGE_LIMIT},signal);
   const rows=page?.items;
   if(!Array.isArray(rows)||rows.length>PAGE_LIMIT||typeof page.providerLimitReached!=='boolean')throw Error('calendar_week_invalid_source');
   if(page.providerLimitReached||rows.length===PAGE_LIMIT){
    if(depth>=MAX_DEPTH||to-from<3600000)throw Error('calendar_week_incomplete');
    const middle=from+Math.floor((to-from)/2);
    await collect(from,middle,depth+1);await collect(middle,to,depth+1);return;
   }
   for(const row of rows){
    const start=eventStart(row?.start);
    if(!start)throw Error('calendar_week_invalid_source');
    if(start.getTime()<from||start.getTime()>=to||row.status==='cancelled')continue;
    const key=row.calendarId&&row.id?JSON.stringify([row.calendarId,row.id,row.start]):JSON.stringify([row.summary,row.start,row.end]);
    found.set(key,{event:row,start});
   }
  }
  const first=new Date(intent.start);
  for(let day=0;day<7;day++){
   const from=new Date(first.getFullYear(),first.getMonth(),first.getDate()+day).getTime();
   const to=new Date(first.getFullYear(),first.getMonth(),first.getDate()+day+1).getTime();
   await collect(from,to,0);
  }
  const sorted=[...found.values()].sort((a,b)=>a.start-b.start||String(a.event.summary??'').localeCompare(String(b.event.summary??'')));
  const lastDay=new Date(first.getFullYear(),first.getMonth(),first.getDate()+6);
  const heading=`Calendar events starting ${dateFormat.format(first)} through ${dateFormat.format(lastDay)} (Mac local time):`;
  const text=sorted.length?`${heading}\n${sorted.map(({event,start})=>eventLine(event,start)).join('\n')}`:`${heading}\nNo events were returned by the connected Google calendars.`;
  if(Buffer.byteLength(text)>32768)throw Error('calendar_week_incomplete');
  return {text,count:sorted.length,reads};
 };
}

export function createCalendarBrokerReader({socketPath=join(process.env.VINCEAI_CACHE_DIR??join(process.env.HOME??'', '.cache/vinceai'),'calendar-read.sock')}={}){
 return (args,signal)=>new Promise((resolve,reject)=>{
  const path='/events?'+new URLSearchParams({calendar:args.calendar,from:args.from,to:args.to,limit:String(args.limit)});
  const req=http.request({socketPath,path,method:'GET',timeout:15000,signal},res=>{
   const chunks=[];let bytes=0;
   res.on('data',part=>{bytes+=part.length;if(bytes>96*1024){req.destroy(Error('calendar_week_response_limit'));return;}chunks.push(part);});
   res.on('end',()=>{try{if(res.statusCode!==200)throw Error('calendar_week_read_failed');const body=JSON.parse(Buffer.concat(chunks).toString('utf8'));if(body?.ok!==true||body.source!=='google_calendar'||!Array.isArray(body.data)||typeof body.providerLimitReached!=='boolean')throw Error('calendar_week_invalid_source');resolve({items:body.data,providerLimitReached:body.providerLimitReached});}catch(error){reject(error);}});
  });
  req.on('timeout',()=>req.destroy(Error('calendar_week_timeout')));
  req.on('error',reject);
  req.end();
 });
}
