import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {calendarWeekIntent,createCalendarWeekAgenda,createCalendarBrokerReader} from '../plugin/calendar-week.mjs';

const local=(day,hour=0)=>new Date(2026,8,day,hour).toISOString();
const event=(day,hour,id,extra={})=>({calendarId:'synthetic',id,summary:`Event ${id}`,start:local(day,hour),end:local(day,hour+1),...extra});

test('calendar week intent uses Monday through Sunday, not a rolling seven days',()=>{
 const at=new Date(2026,8,25,12); // Friday
 const thisWeek=calendarWeekIntent('What’s on my calendar for this week? List the event names and times.',at);
 assert.ok(thisWeek);
 assert.equal(new Date(thisWeek.start).getDate(),21);
 assert.equal(new Date(thisWeek.end).getDate(),28);
 const nextWeek=calendarWeekIntent('Show my calendar next week.',at);
 assert.equal(new Date(nextWeek.start).getDate(),28);
 assert.equal(calendarWeekIntent('Find only my meeting with Alice this week.',at),null);
 assert.equal(calendarWeekIntent('How can I create a calendar event this week?',at),null);
});

test('weekly agenda makes unfiltered day reads and lists every returned event',async()=>{
 const calls=[];
 const agenda=createCalendarWeekAgenda({readEvents:async args=>{calls.push(args);const day=new Date(args.from).getDate();return {items:day===21?[event(21,9,'one'),{calendarId:'synthetic',id:'all-day',summary:'All-day item',start:'2026-09-21',end:'2026-09-22',allDay:true}]:day===23?[event(23,14,'two')]:[],providerLimitReached:false};}});
 const result=await agenda(calendarWeekIntent('List my calendar events this week.',new Date(2026,8,25,12)));
 assert.equal(result.count,3);
 assert.equal(calls.length,7);
 assert.ok(calls.every(call=>call.calendar==='all'&&call.limit===20&&!Object.hasOwn(call,'query')));
 assert.match(result.text,/Monday, September 21, 2026.*09:00.*Event one/);
 assert.match(result.text,/Monday, September 21, 2026.*All day.*All-day item/);
 assert.match(result.text,/Wednesday, September 23, 2026.*14:00.*Event two/);
 assert.doesNotMatch(result.text,/September 29/);
});

test('a full broker page is split and deduplicated before declaring completion',async()=>{
 const calls=[];
 const agenda=createCalendarWeekAgenda({readEvents:async args=>{
  calls.push(args);
  const from=new Date(args.from),to=new Date(args.to);
  if(from.getDate()!==23)return {items:[],providerLimitReached:false};
  if(to-from>=23*3600000)return {items:[event(23,8,'a')],providerLimitReached:true};
  return {items:from.getHours()<12?[event(23,8,'a'),event(23,9,'b')]:[event(23,14,'c'),event(23,14,'c')],providerLimitReached:false};
 }});
 const result=await agenda(calendarWeekIntent('Show my calendar this week.',new Date(2026,8,25,12)));
 assert.equal(result.count,3);
 assert.equal(calls.length,9);
});

test('an unresolved page cap refuses a partial weekly agenda',async()=>{
 const agenda=createCalendarWeekAgenda({readEvents:async()=>({items:[],providerLimitReached:true})});
 await assert.rejects(()=>agenda(calendarWeekIntent('List my calendar events this week.',new Date(2026,8,25,12))),/calendar_week_incomplete/);
});

test('the Unix broker reader requires the raw provider cap signal',async()=>{
 const dir=mkdtempSync(join(tmpdir(),'sanctum-calendar-')),socketPath=join(dir,'calendar.sock');
 let capped=true;
 const server=http.createServer((request,response)=>{
  assert.match(request.url,/calendar=all/);
  assert.doesNotMatch(request.url,/\bq=/);
  response.setHeader('Content-Type','application/json');
  response.end(JSON.stringify({ok:true,source:'google_calendar',data:[],...(capped?{providerLimitReached:false}:{})}));
 });
 try{
  await new Promise(resolve=>server.listen(socketPath,resolve));
  const read=createCalendarBrokerReader({socketPath});
  const args={calendar:'all',from:local(21),to:local(22),limit:20};
  assert.deepEqual(await read(args),{items:[],providerLimitReached:false});
  capped=false;
  await assert.rejects(()=>read(args),/calendar_week_invalid_source/);
 }finally{
  await new Promise(resolve=>server.close(resolve));rmSync(dir,{recursive:true,force:true});
 }
});
