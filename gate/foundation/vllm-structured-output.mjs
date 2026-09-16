/* Pinned vLLM 0.20.1 Outlines JSON-schema compatibility boundary. */
import {canonical} from './contracts.mjs';

export const VLLM_STRUCTURED_DIALECT='vllm-0.20.1-outlines';
const schemaKeywords=new Set(['type','properties','required','additionalProperties','oneOf','const','enum','minLength','maxLength','minimum','maximum','items','minItems','maxItems','pattern']);

export function incompatibleVllmPattern(pattern){
 if(typeof pattern!=='string')return 'PATTERN_TYPE';
 if(/\(\?(?:[=!]|<[=!])/.test(pattern))return 'REGEX_LOOKAROUND';
 if(/\\(?:[1-9]|k[<{'])/.test(pattern))return 'REGEX_BACKREFERENCE';
 if(/\\[bB]/.test(pattern))return 'REGEX_UNICODE_BOUNDARY';
 if(/^\^/.test(pattern))return 'REGEX_PREFIX_CONTEXT';
 return null;
}

function visit(schema,path,mode,omitted){
 if(!schema||typeof schema!=='object'||Array.isArray(schema))throw Error('structured_schema_node');
 const out={};
 for(const key of Object.keys(schema)){
   if(!schemaKeywords.has(key))throw Error('structured_schema_keyword');
   const value=schema[key];
   if(key==='pattern'){
     const reason=incompatibleVllmPattern(value);
     if(reason){
       if(mode==='validate')throw Error('structured_schema_pattern');
       omitted.push({path:path.join('.'),keyword:'pattern',reason});continue;
     }
   }
   if(key==='properties'){
     if(!value||typeof value!=='object'||Array.isArray(value))throw Error('structured_schema_properties');
     out[key]=Object.fromEntries(Object.keys(value).sort().map(name=>[name,visit(value[name],[...path,'properties',name],mode,omitted)]));continue;
   }
   if(key==='oneOf'){
     if(!Array.isArray(value)||!value.length)throw Error('structured_schema_oneof');
     out[key]=value.map((item,index)=>visit(item,[...path,'oneOf',String(index)],mode,omitted));continue;
   }
   if(key==='items'){
     out[key]=visit(value,[...path,'items'],mode,omitted);continue;
   }
   out[key]=structuredClone(value);
 }
 return out;
}

export function validateVllmGenerationSchema(schema){
 try{visit(schema,[], 'validate',[]);return {ok:true,dialect:VLLM_STRUCTURED_DIALECT};}
 catch(error){return {ok:false,dialect:VLLM_STRUCTURED_DIALECT,code:error.message};}
}

export function projectVllmGenerationSchema(authoritativeSchema){
 const omitted=[];
 const schema=visit(authoritativeSchema,[],'project',omitted);
 const checked=validateVllmGenerationSchema(schema);
 if(!checked.ok)throw Error(checked.code);
 return {dialect:VLLM_STRUCTURED_DIALECT,schema,omitted:Object.freeze(omitted.map(Object.freeze)),stable:canonical(schema)};
}
