/* Host-owned child setup, before any repository import. */
'use strict';
const assert=require('node:assert');
const strict=require('node:assert/strict');
const test=require('node:test');
// The oracle and implementation share a JS process. Lock the assertion/test
// interfaces before loading either; ordinary imports cannot replace the oracle.
for(const api of [assert,strict,test]){
 for(const value of Object.values(api))if(typeof value==='function')Object.freeze(value);
 Object.freeze(api);
}
require('node:module').syncBuiltinESMExports();
