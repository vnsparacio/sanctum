// Local command transport only. No model, tool, provider or arbitrary RPC selection.
import { readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { randomUUID } from 'node:crypto';
import { t as GatewayClient } from '@OPENCLAW@/dist/client-BBWFfmhX.js';
import { n as loadDeviceIdentityIfPresent } from '@OPENCLAW@/dist/device-identity-BP5V9Wxb.js';

// Ordinary local execution is bounded at 270 seconds. Keep this transport alive
// beyond that deadline so it never becomes the component that cancels MLX.
const RESPONSE_TIMEOUT_MS=300000;
let client, done=false;
const timer=setTimeout(()=>finish({ok:false,reason:'deadline'}),RESPONSE_TIMEOUT_MS);
function finish(result) {
  if(done)return;done=true;clearTimeout(timer);
  client?.stop();process.stdout.write(JSON.stringify(result)+'\n');
}
try {
  let input='';
  for await(const part of process.stdin){input+=part;if(Buffer.byteLength(input)>40000)throw Error();}
  const data=JSON.parse(input);
  if(Object.keys(data).sort().join(',')!=='command,session' || !/^[a-f0-9]{64}$/.test(data.session)
      || typeof data.command!=='string' || !/^\/(?:gate|work)(?:\s|$)/.test(data.command)
      || Buffer.byteLength(data.command)>32768)throw Error();
  const cfg=JSON.parse(readFileSync('@CONFIG@/openclaw.json','utf8'));
  if(cfg.gateway?.bind!=='loopback' || cfg.gateway?.auth?.mode!=='token' || !cfg.gateway.auth.token)throw Error();
  const gatePath='@GATE@/plugin';
  if(cfg.plugins?.enabled===false || cfg.plugins?.entries?.['hybrid-ai-prompt-gate']?.enabled!==true
      || !cfg.plugins?.load?.paths?.includes(gatePath) || cfg.plugins?.deny?.includes('hybrid-ai-prompt-gate'))throw Error();
  const runId=randomUUID();
  const sessionKey='agent:main:openwebui-gate-'+data.session;
  client=new GatewayClient({
    url:'ws://127.0.0.1:'+cfg.gateway.port,token:cfg.gateway.auth.token,
    clientName:'cli',mode:'cli',scopes:['operator.admin'],deviceIdentity:loadDeviceIdentityIfPresent(),
    onHelloOk:async()=>{
      try{await client.request('chat.send',{sessionKey,message:data.command,idempotencyKey:runId});}
      catch{finish({ok:false});}
    },
    onEvent:event=>{
      const p=event.payload;
      if(event.event!=='chat' || p?.runId!==runId)return;
      if(['error','aborted'].includes(p.state))return finish({ok:false});
      if(p.state==='final'){
        const content=p.message?.content;
        const text=typeof content==='string'?content:Array.isArray(content)?content.map(v=>v.type==='text'?v.text:'').join(''):'';
        finish(text && Buffer.byteLength(text)<100000?{ok:true,text}:{ok:false});
      }
    },
    onConnectError:()=>finish({ok:false}),onClose:()=>finish({ok:false})
  });
  client.start();
}catch{finish({ok:false});}
