/* Bounded model-authored summaries, never authority or hidden reasoning. */
export const NOTE_FIELDS=Object.freeze(['subgoal','evidence','expected_outcome','next_validation']);
export function decisionNoteSchema(){return {type:'object',properties:Object.fromEntries(NOTE_FIELDS.map(key=>[key,{type:'string',minLength:1,maxLength:240}])),required:[...NOTE_FIELDS],additionalProperties:false};}
export function validDecisionNote(value){return !!value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).length===NOTE_FIELDS.length&&NOTE_FIELDS.every(key=>typeof value[key]==='string'&&value[key].trim().length>0&&value[key].length<=240);}
export function detachDecisionNote(value){
 if(!value||typeof value!=='object'||Array.isArray(value)||!Object.hasOwn(value,'decision_note'))return {value,status:'MISSING',note:null};
 const {decision_note,...action}=value;
 return {value:action,status:validDecisionNote(decision_note)?'RECORDED':'INVALID',note:validDecisionNote(decision_note)?Object.fromEntries(NOTE_FIELDS.map(key=>[key,decision_note[key]])):null};
}
