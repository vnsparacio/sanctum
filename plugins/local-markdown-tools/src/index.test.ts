import {describe,expect,it} from 'vitest';
import entry from './index.js';
import {getToolPluginMetadata} from 'openclaw/plugin-sdk/tool-plugin';
describe('scoped markdown tool',()=>{
 it('keeps one save operation without a caller-chosen path',()=>{
  const tools=getToolPluginMetadata(entry)!.tools;
  expect(tools.map(t=>t.name)).toEqual(['save_local_markdown']);
  const properties=tools[0].parameters.properties as Record<string,unknown>;
  expect(properties.path).toBeUndefined();
  expect(tools[0].parameters.additionalProperties).toBe(false);
 });
});
