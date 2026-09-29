/* Networkless Qwen Code model relay. The Mac validates every stdio request. */
import http from 'node:http';
import {readFileSync,createWriteStream,appendFileSync} from 'node:fs';
import {spawn} from 'node:child_process';
import readline from 'node:readline';

const MAX_REQUEST=2*1024*1024,MAX_RESPONSE=16*1024*1024;
const model=process.env.QWEN_MODEL;
if(!/^[A-Za-z0-9_.-]{1,128}$/.test(model??''))throw Error('qwen_model_identity');
let next=1,child=null,done=false;
const pending=new Map();
const input=readline.createInterface({input:process.stdin,crlfDelay:Infinity});
input.on('line',line=>{
 if(line.length>MAX_RESPONSE*2){child?.kill('SIGTERM');return;}
 let reply;try{reply=JSON.parse(line);}catch{child?.kill('SIGTERM');return;}
 const response=pending.get(reply.id);if(!response)return;
 pending.delete(reply.id);
 if(!Number.isInteger(reply.status)||reply.status<100||reply.status>599||typeof reply.body!=='string'){
  response.writeHead(502);response.end();child?.kill('SIGTERM');return;
 }
 const body=Buffer.from(reply.body,'base64');
 if(body.length>MAX_RESPONSE){response.writeHead(502);response.end();child?.kill('SIGTERM');return;}
 response.writeHead(reply.status,{'content-type':reply.content_type==='text/event-stream'?'text/event-stream':'application/json'});
 response.end(body);
});
const server=http.createServer((request,response)=>{
 const route=request.url;
 if(!((route==='/v1/models'&&request.method==='GET')||(route==='/v1/chat/completions'&&request.method==='POST'))||pending.size>=2){response.writeHead(403);response.end();return;}
 const chunks=[];let size=0;
 request.on('data',chunk=>{size+=chunk.length;if(size>MAX_REQUEST){request.destroy();child?.kill('SIGTERM');return;}chunks.push(chunk);});
 request.on('end',()=>{
  let body=Buffer.concat(chunks);
  if(route==='/v1/chat/completions'){
   appendFileSync('/evidence/original-requests.jsonl',body.toString('utf8')+'\n',{mode:0o600});
   let value;try{value=JSON.parse(body.toString('utf8'));}catch{response.writeHead(400);response.end();return;}
   if(value.model!==model){response.writeHead(403);response.end();return;}
   Object.assign(value,{max_tokens:4096,temperature:0.7,top_p:0.8,top_k:20,min_p:0,presence_penalty:1.5,repetition_penalty:1,chat_template_kwargs:{enable_thinking:false},stream_options:{include_usage:true}});
   body=Buffer.from(JSON.stringify(value));
  }
  const id=next++;pending.set(id,response);
  process.stdout.write(JSON.stringify({id,method:request.method,path:route,body:body.toString('base64')})+'\n');
 });
});
await new Promise(resolve=>server.listen(38080,'127.0.0.1',resolve));
const prompt=readFileSync('/poc/prompt.txt','utf8');
const args=['--auth-type','openai','--model',model,'--openai-base-url','http://127.0.0.1:38080/v1','--openai-api-key','local-only','--prompt',prompt,'--approval-mode','yolo','--output-format','stream-json','--max-session-turns','48','--max-tool-calls','40','--max-wall-time','20m','--exclude-tools','agent','web_fetch','get_goal','update_goal','notebook_edit'];
const out=createWriteStream('/evidence/qwen.jsonl',{flags:'wx',mode:0o600});
const err=createWriteStream('/evidence/qwen.stderr',{flags:'wx',mode:0o600});
child=spawn('qwen',args,{cwd:'/workspace',env:{PATH:process.env.PATH,HOME:'/home/qwen',QWEN_HOME:'/poc',QWEN_CODE_DISABLE_TELEMETRY:'1',QWEN_CODE_DISABLE_AUTO_UPDATE:'1',QWEN_MODEL:model,OPENAI_API_KEY:'local-only'},stdio:['ignore','pipe','pipe']});
child.stdout.pipe(out);child.stderr.pipe(err);
child.on('exit',(code,signal)=>{
 if(done)return;done=true;
 process.stdout.write(JSON.stringify({done:true,code,signal})+'\n');
 input.close();server.close();
 setTimeout(()=>process.exit(0),100).unref();
});
process.on('SIGTERM',()=>{child?.kill('SIGTERM');setTimeout(()=>child?.kill('SIGKILL'),2000).unref();});
